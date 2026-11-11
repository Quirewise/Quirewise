#include "page_routes.h"

#include <quirewise/caj.h>
#include <quirewise/ceb.h>
#include <quirewise/djvu.h>
#include <quirewise/image.h>
#include <quirewise/status.h>
#include <quirewise/uvz_parser.h>

#include <pdg.h>
#include <pdz_pdf.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define QW_PAGE_ROUTE_MAX_INPUT (512u * 1024u * 1024u)

static int page_is_pdf(const uint8_t *data, size_t size)
{
    return data && size >= 5u && memcmp(data, "%PDF-", 5u) == 0;
}

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

static int page_convert_uvz(const uint8_t *data, size_t size,
                            const QwAppOptions *options,
                            uint8_t **out_pdf, size_t *out_size,
                            QwConvertReport *report)
{
    QwUvzDocument *document = NULL;
    QwUvzStatus status;
    size_t page_count;
    size_t page_index;
    size_t decoded = 0u;
    QwImage *images = NULL;
    PdgImage *pdg_images = NULL;
    unsigned char *kinds = NULL;
    QwRasterPage *pages = NULL;
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
    images = (QwImage *)calloc(page_count, sizeof(QwImage));
    pdg_images = (PdgImage *)calloc(page_count, sizeof(PdgImage));
    kinds = (unsigned char *)calloc(page_count, 1u);
    pages = (QwRasterPage *)calloc(page_count, sizeof(QwRasterPage));
    if (!images || !pdg_images || !kinds || !pages) {
        free(images);
        free(pdg_images);
        free(kinds);
        free(pages);
        qw_uvz_document_close(document);
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    for (page_index = 0u; page_index < page_count; ++page_index) {
        QwUvzPageInfo info;
        uint8_t *page_data = NULL;
        size_t page_size = 0u;
        QwImage image;
        PdgImage pdg_image;
        int image_status;
        int pdg_status;
        memset(&info, 0, sizeof(info));
        if (qw_uvz_document_page_info(document, page_index, &info) ==
                QW_UVZ_OK &&
            info.is_blank)
            continue;
        status = qw_uvz_document_read_page(document, page_index, &page_data,
                                           &page_size);
        if (status != QW_UVZ_OK || !page_data) continue;
        memset(&image, 0, sizeof(image));
        image_status = qw_image_decode(page_data, page_size, &image);
        if (image_status == QW_IMAGE_OK) {
            images[decoded] = image;
            pages[decoded].pixels = image.pixels;
            pages[decoded].stride = image.stride;
            pages[decoded].width = image.width;
            pages[decoded].height = image.height;
            pages[decoded].channels =
                image.format == QW_IMAGE_PIXEL_RGB24 ? 3 : 1;
            kinds[decoded] = 1u;
            ++decoded;
        } else {
            memset(&pdg_image, 0, sizeof(pdg_image));
            pdg_status = pdg_render_memory(page_data, page_size, &pdg_image);
            if (pdg_status == PDG_OK) {
                pdg_images[decoded] = pdg_image;
                pages[decoded].pixels = pdg_image.pixels;
                pages[decoded].stride = pdg_image.stride;
                pages[decoded].width = pdg_image.width;
                pages[decoded].height = pdg_image.height;
                pages[decoded].channels =
                    pdg_image.format == PDG_PIXEL_RGB24 ? 3 : 1;
                kinds[decoded] = 2u;
                ++decoded;
            }
        }
        qw_uvz_page_data_free(page_data);
    }
    qw_uvz_document_close(document);
    if (decoded == 0u) {
        free(images);
        free(pdg_images);
        free(kinds);
        free(pages);
        if (report) snprintf(report->note, sizeof(report->note),
                             "UVZ pages could not be decoded as images or PDG");
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    rc = qw_raster_pages_to_pdf_mode(pages, decoded, options->raster_page_mode,
                                     out_pdf, out_size, report);
    for (page_index = 0u; page_index < decoded; ++page_index) {
        if (kinds[page_index] == 1u) qw_image_free(&images[page_index]);
        else if (kinds[page_index] == 2u) pdg_image_free(&pdg_images[page_index]);
    }
    free(images);
    free(pdg_images);
    free(kinds);
    free(pages);
    return rc;
}

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
        PdzPdfReport pdz_report;
        int status;
        int page_mode = options->raster_page_mode == QW_RASTER_PAGE_MODE_A4
                            ? PDZ_PDF_PAGE_A4
                            : PDZ_PDF_PAGE_IMAGE;
        memset(&pdz_report, 0, sizeof(pdz_report));
        status = pdz_pdf_from_pdz(data, size, NULL, options->pdz_page_rule,
                                  page_mode, out_pdf, out_size, &pdz_report);
        if (status != 0) {
            if (report) snprintf(report->note, sizeof(report->note),
                                 "PDG container conversion failed with status %d",
                                 status);
            return QW_STATUS_ERR_FORMAT;
        }
        if (report) {
            snprintf(report->note, sizeof(report->note),
                     "PDG image pages converted (%zu pages written)",
                     pdz_report.pages_written);
            report->pages_written = pdz_report.pages_written;
            report->output_size = *out_size;
        }
        return page_is_pdf(*out_pdf, *out_size) ? QW_STATUS_OK
                                                : QW_STATUS_ERR_FORMAT;
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
