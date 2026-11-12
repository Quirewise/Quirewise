#include "page_routes.h"

#include <quirewise/caj.h>
#include <quirewise/ceb.h>
#include <quirewise/convert.h>
#include <quirewise/djvu.h>
#include <quirewise/image.h>
#include <quirewise/pdf.h>
#include <quirewise/status.h>
#include <quirewise/uvz_parser.h>

#include <pdg.h>
#include <pdz_pdf.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define QW_PAGE_ROUTE_MAX_INPUT (512u * 1024u * 1024u)

/*
 * PDF payload pages are rasterised through the internal PDF engine in
 * quirewise-document (the single PDF implementation owned by the workspace),
 * never through an external rasteriser.  PDG page routes embed raster pages at
 * PDZ_PDF_DPI (300 dpi), so rendering at the same resolution keeps the page
 * geometry of an embedded PDF page identical to its source page.
 */
#define QW_PAGE_PDF_RENDER_DPI 300u

/* Transient raster cap for one page: far above any scanned page, low enough
 * that a hostile MediaBox cannot exhaust memory before the renderer does. */
#define QW_PAGE_PDF_RASTER_LIMIT ((size_t)512u * 1024u * 1024u)

static int page_is_pdf(const uint8_t *data, size_t size)
{
    return data && size >= 5u && memcmp(data, "%PDF-", 5u) == 0;
}

static int page_status_from_pdg(int rc)
{
    switch (rc) {
    case PDG_OK:
        return QW_STATUS_OK;
    case PDG_ERR_INVALID_ARGUMENT:
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    case PDG_ERR_OUT_OF_MEMORY:
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    case PDG_ERR_IO:
        return QW_STATUS_ERR_IO;
    case PDG_ERR_EMPTY:
        return QW_STATUS_ERR_EMPTY;
    case PDG_ERR_RESOURCE_LIMIT:
        return QW_STATUS_ERR_RESOURCE_LIMIT;
    case PDG_ERR_UNSUPPORTED:
    case PDG_ERR_EXTERNAL_DECODER_REQUIRED:
    case PDG_ERR_NOT_PDZ:
        return QW_STATUS_ERR_UNSUPPORTED;
    case PDG_ERR_FORMAT:
    case PDG_ERR_DECODE:
    case PDG_ERR_NOT_PDG:
        return QW_STATUS_ERR_FORMAT;
    default:
        return QW_STATUS_ERR_DECODE;
    }
}

static int page_status_is_stable(int status)
{
    switch (status) {
    case QW_STATUS_ERR_INVALID_ARGUMENT:
    case QW_STATUS_ERR_OUT_OF_MEMORY:
    case QW_STATUS_ERR_IO:
    case QW_STATUS_ERR_FORMAT:
    case QW_STATUS_ERR_UNSUPPORTED:
    case QW_STATUS_ERR_DECODE:
    case QW_STATUS_ERR_EMPTY:
    case QW_STATUS_ERR_EXTERNAL_DECODER_REQUIRED:
    case QW_STATUS_ERR_RESOURCE_LIMIT:
        return 1;
    default:
        return 0;
    }
}

/*
 * Rasterise the first page of a PDF payload with the package-local PDF engine.
 * A PDG page represents exactly one page, so only page 1 is rendered; a page
 * payload with several pages keeps its first page and the caller records the
 * route loss in the report note.
 */
static int page_pdf_first_page(const uint8_t *data, size_t size,
                               QwRasterPage *out, QwConvertReport *report)
{
    QwPdfDocument *document = NULL;
    size_t page_count = 0u;
    QwConvertReport open_report;
    QwConvertReport render_report;
    QwPageImage image;
    double media[4] = {0.0, 0.0, 0.0, 0.0};
    double crop[4] = {0.0, 0.0, 0.0, 0.0};
    int rotation = 0;
    int status;

    if (!data || !size || !out) {
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));
    memset(&open_report, 0, sizeof(open_report));
    memset(&render_report, 0, sizeof(render_report));
    memset(&image, 0, sizeof(image));

    status = qw_pdf_open(data, size, &document, &page_count, &open_report);
    if (status != QW_STATUS_OK || !document || page_count == 0u) {
        if (report) {
            snprintf(report->note, sizeof(report->note),
                     "PDF payload could not be opened (%s)",
                     open_report.note[0] ? open_report.note : "no pages");
        }
        if (document) {
            qw_pdf_close(document);
        }
        return page_status_is_stable(status) ? status : QW_STATUS_ERR_FORMAT;
    }

    if (qw_pdf_page_geometry(document, 0u, media, crop, &rotation) ==
        QW_STATUS_OK) {
        double width_points = media[2] - media[0];
        double height_points = media[3] - media[1];
        if (width_points > 0.0 && height_points > 0.0) {
            double width = width_points * (double)QW_PAGE_PDF_RENDER_DPI / 72.0;
            double height = height_points * (double)QW_PAGE_PDF_RENDER_DPI / 72.0;
            if (width > 100000.0 || height > 100000.0 ||
                width * height * 3.0 > (double)QW_PAGE_PDF_RASTER_LIMIT) {
                qw_pdf_close(document);
                if (report) {
                    snprintf(report->note, sizeof(report->note),
                             "PDF payload page is too large to rasterise at "
                             "%u dpi",
                             (unsigned int)QW_PAGE_PDF_RENDER_DPI);
                }
                return QW_STATUS_ERR_RESOURCE_LIMIT;
            }
        }
    }

    status = qw_pdf_render_page(document, 0u, QW_PAGE_PDF_RENDER_DPI, &image,
                                &render_report);
    qw_pdf_close(document);
    if (status != QW_STATUS_OK || !image.data || !image.width || !image.height ||
        image.kind != QW_PAGE_IMAGE_RGB24) {
        if (report) {
            snprintf(report->note, sizeof(report->note),
                     "PDF payload page 1 could not be rasterised (%s)",
                     render_report.note[0] ? render_report.note : "no raster");
        }
        qw_pdf_page_free(&image);
        return page_status_is_stable(status) ? status : QW_STATUS_ERR_FORMAT;
    }

    out->pixels = image.data;
    out->stride = (size_t)image.width * 3u;
    out->width = image.width;
    out->height = image.height;
    out->channels = 3;
    image.data = NULL; /* ownership moved to the caller */
    qw_pdf_page_free(&image);
    if (report && render_report.note[0]) {
        snprintf(report->note, sizeof(report->note),
                 "PDF payload rasterised: %s", render_report.note);
    }
    return QW_STATUS_OK;
}

/*
 * Decrypt a PDG page blob and, when its payload is a PDF, rasterise page 1.
 * Returns the stable status for a payload that is not a PDF.
 */
static int page_pdf_from_pdg_blob(const uint8_t *data, size_t size,
                                  QwRasterPage *out, QwConvertReport *report)
{
    PdgBuffer payload;
    int rc;

    if (!data || !size || !out) {
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));
    memset(&payload, 0, sizeof(payload));
    rc = pdg_decrypt_memory(data, size, &payload);
    if (rc != PDG_OK) {
        return page_status_from_pdg(rc);
    }
    if (payload.kind != PDG_OUTPUT_PDF) {
        pdg_buffer_free(&payload);
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    rc = page_pdf_first_page(payload.data, payload.size, out, report);
    pdg_buffer_free(&payload);
    return rc;
}

/*
 * Rasterise one standalone page payload: a direct PDF file, a PDG page blob
 * whose payload is a PDF, or any payload the PDG decoder already renders.
 */
static int page_rasterize_payload(const uint8_t *data, size_t size,
                                  QwRasterPage *out, QwConvertReport *report)
{
    PdgImage image;
    size_t row_bytes;
    uint8_t *pixels;
    int channels;
    int rc;

    if (!data || !size || !out) {
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    }
    memset(out, 0, sizeof(*out));
    if (page_is_pdf(data, size)) {
        return page_pdf_first_page(data, size, out, report);
    }

    memset(&image, 0, sizeof(image));
    rc = pdg_render_memory(data, size, &image);
    if (rc == PDG_ERR_EXTERNAL_DECODER_REQUIRED) {
        return page_pdf_from_pdg_blob(data, size, out, report);
    }
    if (rc != PDG_OK) {
        return page_status_from_pdg(rc);
    }
    if (!image.pixels || !image.width || !image.height) {
        pdg_image_free(&image);
        return QW_STATUS_ERR_FORMAT;
    }
    channels = image.format == PDG_PIXEL_RGB24 ? 3 : 1;
    row_bytes = (size_t)image.width * (size_t)channels;
    out->stride = row_bytes;
    out->width = image.width;
    out->height = image.height;
    out->channels = channels;
    if (image.stride && (size_t)image.stride != row_bytes) {
        size_t rows = (size_t)image.height;
        size_t index;
        pixels = (uint8_t *)malloc(row_bytes * rows);
        if (!pixels) {
            pdg_image_free(&image);
            memset(out, 0, sizeof(*out));
            return QW_STATUS_ERR_OUT_OF_MEMORY;
        }
        for (index = 0u; index < rows; ++index) {
            memcpy(pixels + index * row_bytes,
                   image.pixels + index * (size_t)image.stride, row_bytes);
        }
        out->pixels = pixels;
    } else {
        out->pixels = image.pixels;
        image.pixels = NULL; /* ownership moved to the caller */
    }
    pdg_image_free(&image);
    return QW_STATUS_OK;
}

/* A decoded still image as a tightly packed raster page. */
static int page_raster_from_image(QwImage *image, QwRasterPage *out)
{
    size_t row_bytes;
    size_t rows;
    size_t index;
    uint8_t *pixels;
    int channels;

    if (!image || !image->pixels || !image->width || !image->height || !out) {
        return 0;
    }
    channels = image->format == QW_IMAGE_PIXEL_RGB24 ? 3 : 1;
    row_bytes = (size_t)image->width * (size_t)channels;
    rows = (size_t)image->height;
    memset(out, 0, sizeof(*out));
    out->width = image->width;
    out->height = image->height;
    out->channels = channels;
    out->stride = row_bytes;
    if (image->stride == 0 || image->stride == row_bytes) {
        out->pixels = image->pixels;
        image->pixels = NULL;
        return 1;
    }
    pixels = (uint8_t *)malloc(row_bytes * rows);
    if (!pixels) {
        return 0;
    }
    for (index = 0u; index < rows; ++index) {
        memcpy(pixels + index * row_bytes,
               image->pixels + index * image->stride, row_bytes);
    }
    out->pixels = pixels;
    return 1;
}

/* ------------------------------------------------------------ raster list -- */

typedef struct QwPageRasterList {
    QwRasterPage *pages;
    size_t count;
    size_t capacity;
} QwPageRasterList;

static int page_raster_list_push(QwPageRasterList *list, QwRasterPage page)
{
    if (list->count == list->capacity) {
        size_t capacity = list->capacity ? list->capacity * 2u : 16u;
        QwRasterPage *grown = (QwRasterPage *)realloc(
            list->pages, capacity * sizeof(*grown));
        if (!grown) {
            return 0;
        }
        list->pages = grown;
        list->capacity = capacity;
    }
    list->pages[list->count++] = page;
    return 1;
}

static void page_raster_list_release(QwPageRasterList *list)
{
    size_t index;
    for (index = 0u; index < list->count; ++index) {
        free((void *)list->pages[index].pixels);
    }
    free(list->pages);
    memset(list, 0, sizeof(*list));
}

/*
 * Embed the collected rasters through the PDZ PDF writer. The writer sizes a
 * page at PDZ_PDF_DPI, which is the convention both PDG page routes use, and
 * scales the image content stream accordingly (the document raster writer's
 * IMAGE mode draws the unit square instead, so it is not used here).
 */
static int page_rasters_to_pdf(QwPageRasterList *rasters, int page_mode,
                               uint8_t **out_pdf, size_t *out_size,
                               size_t *out_pages, QwConvertReport *report)
{
    PdzPdfImage *images;
    size_t index;
    int rc;

    if (!rasters || !rasters->count) {
        return QW_STATUS_ERR_EMPTY;
    }
    images = (PdzPdfImage *)calloc(rasters->count, sizeof(*images));
    if (!images) {
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    for (index = 0u; index < rasters->count; ++index) {
        images[index].data = rasters->pages[index].pixels;
        images[index].size = (size_t)rasters->pages[index].stride *
                             (size_t)rasters->pages[index].height;
        images[index].kind = rasters->pages[index].channels == 3
                                 ? QW_PAGE_IMAGE_RGB24
                                 : QW_PAGE_IMAGE_GRAY8;
        images[index].width = rasters->pages[index].width;
        images[index].height = rasters->pages[index].height;
    }
    rc = pdz_pdf_from_images(images, rasters->count, page_mode, out_pdf,
                             out_size, out_pages);
    free(images);
    if (rc != PDG_OK) {
        return page_status_from_pdg(rc);
    }
    if (report) {
        report->output_size = *out_size;
        report->pages_written = *out_pages;
    }
    return QW_STATUS_OK;
}

/* --------------------------------------------------------------- DjVu ----- */

static int page_convert_djvu(const uint8_t *data, size_t size,
                             const QwAppOptions *options,
                             uint8_t **out_pdf, size_t *out_size,
                             QwConvertReport *report)
{
    size_t page_count = 0u;
    size_t page_index;
    QwRasterPage *pages = NULL;
    QwDjvuStatus status;
    int rc;

    if (!qw_djvu_is_supported(data, size)) return QW_STATUS_ERR_UNSUPPORTED;
    status = qw_djvu_get_page_count(data, size, &page_count);
    if (status != QW_DJVU_OK || page_count == 0u) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "DjVu container reports no pages");
        return QW_STATUS_ERR_FORMAT;
    }
    pages = (QwRasterPage *)calloc(page_count, sizeof(QwRasterPage));
    if (!pages) return QW_STATUS_ERR_OUT_OF_MEMORY;
    for (page_index = 0u; page_index < page_count; ++page_index) {
        QwDjvuImage image;
        memset(&image, 0, sizeof(image));
        status = qw_djvu_render_page(data, size, page_index, 1u, &image);
        if (status != QW_DJVU_OK) {
            if (report) snprintf(report->note, sizeof(report->note),
                                 "DjVu page %zu render failed with status %d",
                                 page_index, (int)status);
            while (page_index > 0u) {
                --page_index;
                free((void *)pages[page_index].pixels);
            }
            free(pages);
            if (status == QW_DJVU_ERR_RESOURCE_LIMIT)
                return QW_STATUS_ERR_RESOURCE_LIMIT;
            return QW_STATUS_ERR_FORMAT;
        }
        pages[page_index].pixels = (const uint8_t *)malloc(image.size);
        if (!pages[page_index].pixels) {
            qw_djvu_image_free(&image);
            while (page_index > 0u) {
                --page_index;
                free((void *)pages[page_index].pixels);
            }
            free(pages);
            return QW_STATUS_ERR_OUT_OF_MEMORY;
        }
        memcpy((void *)pages[page_index].pixels, image.pixels, image.size);
        pages[page_index].stride = image.stride;
        pages[page_index].width = (uint32_t)image.width;
        pages[page_index].height = (uint32_t)image.height;
        pages[page_index].channels =
            image.format == QW_DJVU_PIXEL_RGB24 ? 3 : 1;
        qw_djvu_image_free(&image);
    }
    rc = qw_raster_pages_to_pdf_mode(pages, page_count,
                                     options->raster_page_mode, out_pdf,
                                     out_size, report);
    for (page_index = 0u; page_index < page_count; ++page_index)
        free((void *)pages[page_index].pixels);
    free(pages);
    return rc;
}

/* ---------------------------------------------------------------- UVZ ----- */

static int page_convert_uvz(const uint8_t *data, size_t size,
                            const QwAppOptions *options,
                            uint8_t **out_pdf, size_t *out_size,
                            QwConvertReport *report)
{
    QwUvzDocument *document = NULL;
    QwUvzStatus status;
    size_t page_count;
    size_t page_index;
    size_t skipped = 0u;
    size_t written = 0u;
    QwPageRasterList rasters;
    int page_mode;
    int rc;

    if (size < 4u || memcmp(data, "PK\x03\x04", 4u) != 0)
        return QW_STATUS_ERR_UNSUPPORTED;
    status = qw_uvz_document_open(data, size, &document);
    if (status != QW_UVZ_OK || !document) return QW_STATUS_ERR_UNSUPPORTED;
    page_count = qw_uvz_document_page_count(document);
    if (page_count == 0u) {
        qw_uvz_document_close(document);
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    memset(&rasters, 0, sizeof(rasters));
    page_mode = (options && options->raster_page_mode == QW_RASTER_PAGE_MODE_A4)
                    ? PDZ_PDF_PAGE_A4
                    : PDZ_PDF_PAGE_IMAGE;
    for (page_index = 0u; page_index < page_count; ++page_index) {
        QwUvzPageInfo info;
        uint8_t *page_data = NULL;
        size_t page_size = 0u;
        QwImage image;
        QwRasterPage raster;
        int status_code;

        memset(&info, 0, sizeof(info));
        if (qw_uvz_document_page_info(document, page_index, &info) ==
                QW_UVZ_OK &&
            info.is_blank)
            continue;
        status = qw_uvz_document_read_page(document, page_index, &page_data,
                                           &page_size);
        if (status != QW_UVZ_OK || !page_data) continue;
        memset(&image, 0, sizeof(image));
        memset(&raster, 0, sizeof(raster));
        if (qw_image_decode(page_data, page_size, &image) == QW_IMAGE_OK &&
            page_raster_from_image(&image, &raster)) {
            qw_image_free(&image);
            status_code = QW_STATUS_OK;
        } else {
            qw_image_free(&image);
            status_code = page_rasterize_payload(page_data, page_size, &raster,
                                                 report);
        }
        qw_uvz_page_data_free(page_data);
        if (status_code != QW_STATUS_OK) {
            ++skipped;
            continue;
        }
        if (!page_raster_list_push(&rasters, raster)) {
            free((void *)raster.pixels);
            page_raster_list_release(&rasters);
            qw_uvz_document_close(document);
            return QW_STATUS_ERR_OUT_OF_MEMORY;
        }
    }
    qw_uvz_document_close(document);
    if (rasters.count == 0u) {
        page_raster_list_release(&rasters);
        if (report) snprintf(report->note, sizeof(report->note),
                             "UVZ pages could not be decoded as images or PDG");
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    rc = page_rasters_to_pdf(&rasters, page_mode, out_pdf, out_size, &written,
                             report);
    page_raster_list_release(&rasters);
    if (rc == QW_STATUS_OK) {
        if (report) {
            report->pages_written = written;
            report->skipped_pages = skipped;
            snprintf(report->note, sizeof(report->note),
                     "UVZ pages converted (%zu pages written, %zu skipped)",
                     written, skipped);
        }
        return page_is_pdf(*out_pdf, *out_size) ? QW_STATUS_OK
                                                : QW_STATUS_ERR_FORMAT;
    }
    return rc;
}

/* ---------------------------------------------------------------- PDZ ----- */

static int page_member_is_body(const PdzMember *member)
{
    size_t length;
    size_t index;
    if (!member) return 0;
    length = strnlen(member->name, PDZ_NAME_SIZE);
    if (length != 6u) return 0;
    for (index = 0u; index < length; ++index) {
        if (member->name[index] < '0' || member->name[index] > '9') return 0;
    }
    return 1;
}

static int page_member_is_attachment(const PdzMember *member)
{
    size_t length;
    size_t index;
    if (!member) return 0;
    length = strnlen(member->name, PDZ_NAME_SIZE);
    if (length < 4u || strncmp(member->name, "att", 3u) != 0) return 0;
    for (index = 3u; index < length; ++index) {
        if (member->name[index] < '0' || member->name[index] > '9') return 0;
    }
    return 1;
}

static int page_member_selected(const PdzMember *member, int rule)
{
    switch (rule) {
    case PDZ_PDF_PAGES_BODY:
        return page_member_is_body(member);
    case PDZ_PDF_PAGES_BODY_ATT:
        return page_member_is_body(member) || page_member_is_attachment(member);
    case PDZ_PDF_PAGES_ALL:
    default:
        return 1;
    }
}

static int page_convert_pdz(const uint8_t *data, size_t size,
                            const QwAppOptions *options,
                            uint8_t **out_pdf, size_t *out_size,
                            QwConvertReport *report)
{
    PdzMember *members = NULL;
    size_t member_count = 0u;
    size_t index;
    size_t skipped = 0u;
    size_t written = 0u;
    QwPageRasterList rasters;
    int rule = options ? options->pdz_page_rule : PDZ_PDF_PAGES_AUTO;
    int page_mode;
    int rc;

    if (!data || !size || !out_pdf || !out_size) {
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    }
    *out_pdf = NULL;
    *out_size = 0u;
    memset(&rasters, 0, sizeof(rasters));
    page_mode = (options && options->raster_page_mode == QW_RASTER_PAGE_MODE_A4)
                    ? PDZ_PDF_PAGE_A4
                    : PDZ_PDF_PAGE_IMAGE;

    rc = pdz_members(data, size, NULL, 0u, &member_count);
    if (rc != PDG_OK) return page_status_from_pdg(rc);
    if (member_count == 0u) return QW_STATUS_ERR_UNSUPPORTED;
    members = (PdzMember *)calloc(member_count, sizeof(*members));
    if (!members) return QW_STATUS_ERR_OUT_OF_MEMORY;
    rc = pdz_members(data, size, members, member_count, &member_count);
    if (rc != PDG_OK) {
        free(members);
        return page_status_from_pdg(rc);
    }
    if (rule == PDZ_PDF_PAGES_AUTO) rule = PDZ_PDF_PAGES_ALL;

    for (index = 0u; index < member_count; ++index) {
        PdzBuffer payload;
        QwRasterPage page;
        int status;
        if (!page_member_selected(&members[index], rule)) continue;
        memset(&payload, 0, sizeof(payload));
        rc = pdz_member_payload(data, size, &members[index], NULL, &payload);
        if (rc != PDG_OK) {
            ++skipped;
            continue;
        }
        if (pdz_pdfpdg_is_member(payload.data, payload.size)) {
            pdz_buffer_free(&payload);
            if (report) {
                snprintf(report->note, sizeof(report->note),
                         "PDZ native PDF member (pdg_type 0x1A) is not "
                         "supported: merging the publisher PDF is not "
                         "implemented");
            }
            free(members);
            page_raster_list_release(&rasters);
            return QW_STATUS_ERR_UNSUPPORTED;
        }
        memset(&page, 0, sizeof(page));
        status = page_rasterize_payload(payload.data, payload.size, &page,
                                        report);
        pdz_buffer_free(&payload);
        if (status != QW_STATUS_OK) {
            ++skipped;
            continue;
        }
        if (!page_raster_list_push(&rasters, page)) {
            free((void *)page.pixels);
            free(members);
            page_raster_list_release(&rasters);
            return QW_STATUS_ERR_OUT_OF_MEMORY;
        }
    }
    free(members);

    if (rasters.count == 0u) {
        page_raster_list_release(&rasters);
        if (report) snprintf(report->note, sizeof(report->note),
                             "PDZ container produced no page image");
        return QW_STATUS_ERR_UNSUPPORTED;
    }

    rc = page_rasters_to_pdf(&rasters, page_mode, out_pdf, out_size, &written,
                             report);
    page_raster_list_release(&rasters);
    if (rc != QW_STATUS_OK) {
        return rc;
    }
    if (report) {
        report->pages_written = written;
        report->skipped_pages = skipped;
        snprintf(report->note, sizeof(report->note),
                 "PDG pages converted (%zu pages written, %zu skipped)",
                 written, skipped);
    }
    return page_is_pdf(*out_pdf, *out_size) ? QW_STATUS_OK
                                            : QW_STATUS_ERR_FORMAT;
}

/* ------------------------------------------------------------ dispatch ---- */

int qw_app_page_convert(const uint8_t *data, size_t size,
                        const QwAppOptions *options,
                        uint8_t **out_pdf, size_t *out_size,
                        QwConvertReport *report)
{
    static const QwAppOptions defaults = {
        QW_RASTER_PAGE_MODE_IMAGE, 0, NULL, 0u
    };
    if (!data || !size || !out_pdf || !out_size)
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    if (!options) options = &defaults;
    *out_pdf = NULL;
    *out_size = 0u;

    if (size >= 5u && memcmp(data, "%pdgz", 5u) == 0) {
        return page_convert_pdz(data, size, options, out_pdf, out_size, report);
    }
    if (size >= 11u && memcmp(data, "Founder CEB", 11u) == 0) {
        QwCebStatus status = qw_ceb_decrypt_to_pdf(data, size, out_pdf,
                                                   out_size);
        if (status != QW_CEB_OK) {
            if (report) snprintf(report->note, sizeof(report->note),
                                 "CEB PDF extraction failed with status %d",
                                 (int)status);
            return QW_STATUS_ERR_FORMAT;
        }
        if (report) report->output_size = *out_size;
        return page_is_pdf(*out_pdf, *out_size) ? QW_STATUS_OK
                                                : QW_STATUS_ERR_FORMAT;
    }
    if (size >= 3u && memcmp(data, "CAJ", 3u) == 0) {
        QwCajStatus status = qw_caj_extract_classic_pdf(data, size, out_pdf,
                                                        out_size);
        if (status != QW_CAJ_OK) {
            status = qw_caj_decrypt_kdh_pdf(data, size, out_pdf, out_size);
        }
        if (status != QW_CAJ_OK) {
            if (report) snprintf(report->note, sizeof(report->note),
                                 "CAJ PDF extraction failed with status %d",
                                 (int)status);
            return QW_STATUS_ERR_FORMAT;
        }
        if (report) report->output_size = *out_size;
        return page_is_pdf(*out_pdf, *out_size) ? QW_STATUS_OK
                                                : QW_STATUS_ERR_FORMAT;
    }
    if (qw_djvu_is_supported(data, size))
        return page_convert_djvu(data, size, options, out_pdf, out_size,
                                 report);
    if (size >= 4u && memcmp(data, "PK\x03\x04", 4u) == 0)
        return page_convert_uvz(data, size, options, out_pdf, out_size,
                                report);
    return QW_STATUS_ERR_UNSUPPORTED;
}

int qw_app_page_convert_file(const char *path,
                             const QwAppOptions *options,
                             uint8_t **out_pdf, size_t *out_size,
                             QwConvertReport *report)
{
    FILE *file;
    long length;
    uint8_t *data;
    int rc;

    if (!path) return QW_STATUS_ERR_INVALID_ARGUMENT;
    file = fopen(path, "rb");
    if (!file) return QW_STATUS_ERR_IO;
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    if ((unsigned long)length > (unsigned long)QW_PAGE_ROUTE_MAX_INPUT) {
        fclose(file);
        if (report) snprintf(report->note, sizeof(report->note),
                             "page input exceeds the 512 MiB conversion limit");
        return QW_STATUS_ERR_RESOURCE_LIMIT;
    }
    data = (uint8_t *)malloc((size_t)length ? (size_t)length : 1u);
    if (!data) {
        fclose(file);
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    if (length > 0 &&
        fread(data, 1u, (size_t)length, file) != (size_t)length) {
        free(data);
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    fclose(file);
    rc = qw_app_page_convert(data, (size_t)length, options, out_pdf, out_size,
                             report);
    free(data);
    return rc;
}
