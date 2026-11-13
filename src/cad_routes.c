#include "cad_routes.h"

#include <quirewise/cad.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define QW_CAD_ROUTE_MAX_INPUT (256u * 1024u * 1024u)
#define QW_CAD_ROUTE_WIDTH 2048u

static int cad_extension(const char *path)
{
    const char *dot = strrchr(path, '.');
    if (!dot) return 0;
    ++dot;
    if ((dot[0] == 'd' || dot[0] == 'D') &&
        (dot[1] == 'x' || dot[1] == 'X') &&
        (dot[2] == 'f' || dot[2] == 'F') && dot[3] == '\0')
        return 1;
    if ((dot[0] == 'd' || dot[0] == 'D') &&
        (dot[1] == 'w' || dot[1] == 'W') &&
        (dot[2] == 'g' || dot[2] == 'G') && dot[3] == '\0')
        return 2;
    return 0;
}

static int cad_read_file(const char *path, uint8_t **out_data, size_t *out_size,
                         QwConvertReport *report)
{
    FILE *file;
    long length;
    uint8_t *data;
    file = fopen(path, "rb");
    if (!file) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "cannot open %s", path);
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    }
    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    }
    length = ftell(file);
    if (length < 0 || (unsigned long)length > QW_CAD_ROUTE_MAX_INPUT) {
        fclose(file);
        return QW_STATUS_ERR_RESOURCE_LIMIT;
    }
    if (fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    }
    data = (uint8_t *)malloc((size_t)length ? (size_t)length : 1u);
    if (!data) {
        fclose(file);
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    if (length > 0 && fread(data, 1u, (size_t)length, file) != (size_t)length) {
        free(data);
        fclose(file);
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    }
    fclose(file);
    *out_data = data;
    *out_size = (size_t)length;
    return QW_STATUS_OK;
}

static QwStatus cad_status(QwCadStatus status)
{
    switch (status) {
    case QW_CAD_OK: return QW_STATUS_OK;
    case QW_CAD_ERR_INVALID_ARGUMENT: return QW_STATUS_ERR_INVALID_ARGUMENT;
    case QW_CAD_ERR_OUT_OF_MEMORY: return QW_STATUS_ERR_OUT_OF_MEMORY;
    case QW_CAD_ERR_RESOURCE_LIMIT: return QW_STATUS_ERR_RESOURCE_LIMIT;
    case QW_CAD_ERR_UNSUPPORTED: return QW_STATUS_ERR_UNSUPPORTED;
    case QW_CAD_ERR_FORMAT: return QW_STATUS_ERR_FORMAT;
    default: return QW_STATUS_ERR_DECODE;
    }
}

static int cad_parse_file(const char *input_path, QwCadDocument **out_document,
                          QwConvertReport *report)
{
    uint8_t *data = NULL;
    size_t size = 0u;
    QwCadStatus status;
    int rc = cad_read_file(input_path, &data, &size, report);
    if (rc != QW_STATUS_OK) return rc;
    status = qw_cad_parse(data, size, out_document);
    free(data);
    if (status != QW_CAD_OK) {
        if (report) {
            snprintf(report->note, sizeof(report->note),
                     "CAD parse failed: %s", qw_cad_status_string(status));
        }
        return cad_status(status);
    }
    if (report) {
        report->format = QW_FORMAT_UNKNOWN;
        report->pages_written = 1u;
    }
    return QW_STATUS_OK;
}

int qw_app_cad_check_file(const char *input_path, QwConvertReport *report)
{
    QwCadDocument *document = NULL;
    QwCadImage image;
    QwCadStatus status;
    int rc;
    if (cad_extension(input_path) == 0) return QW_STATUS_ERR_UNSUPPORTED;
    rc = cad_parse_file(input_path, &document, report);
    if (rc != QW_STATUS_OK) return rc;
    memset(&image, 0, sizeof(image));
    status = qw_cad_render_rgba(document, 256u, &image);
    qw_cad_image_free(&image);
    qw_cad_document_free(document);
    if (status != QW_CAD_OK) {
        if (report) {
            snprintf(report->note, sizeof(report->note),
                     "CAD render check failed: %s",
                     qw_cad_status_string(status));
        }
        return cad_status(status);
    }
    if (report) {
        snprintf(report->note, sizeof(report->note),
                 "CAD %s parsed and rendered",
                 cad_extension(input_path) == 2 ? "DWG" : "DXF");
    }
    return QW_STATUS_OK;
}

int qw_app_cad_extract_text(const char *input_path, uint8_t **out_text,
                            size_t *out_size, QwConvertReport *report)
{
    QwCadDocument *document = NULL;
    size_t count;
    size_t index;
    char *text;
    size_t used = 0u;
    size_t capacity = 256u;
    int rc;
    if (!out_text || !out_size) return QW_STATUS_ERR_INVALID_ARGUMENT;
    *out_text = NULL;
    *out_size = 0u;
    if (cad_extension(input_path) == 0) return QW_STATUS_ERR_UNSUPPORTED;
    rc = cad_parse_file(input_path, &document, report);
    if (rc != QW_STATUS_OK) return rc;
    count = qw_cad_text_count(document);
    text = (char *)malloc(capacity);
    if (!text) {
        qw_cad_document_free(document);
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    text[0] = '\0';
    for (index = 0u; index < count; ++index) {
        QwCadTextInfo info;
        size_t needed;
        if (qw_cad_text_at(document, index, &info) != QW_CAD_OK) continue;
        needed = info.text_size + 2u;
        if (used + needed + 1u > 8u * 1024u * 1024u) {
            rc = QW_STATUS_ERR_RESOURCE_LIMIT;
            free(text);
            qw_cad_document_free(document);
            return rc;
        }
        while (used + needed + 1u > capacity) capacity *= 2u;
        {
            char *grown = (char *)realloc(text, capacity);
            if (!grown) {
                free(text);
                qw_cad_document_free(document);
                return QW_STATUS_ERR_OUT_OF_MEMORY;
            }
            text = grown;
        }
        memcpy(text + used, info.text, info.text_size);
        used += info.text_size;
        text[used++] = '\n';
    }
    text[used] = '\0';
    qw_cad_document_free(document);
    *out_text = (uint8_t *)text;
    *out_size = used;
    if (report) {
        snprintf(report->note, sizeof(report->note),
                 "CAD text inventory: %zu text entities", count);
        report->format = QW_FORMAT_UNKNOWN;
        report->pages_written = 0u;
    }
    return QW_STATUS_OK;
}

int qw_app_cad_convert_file(const char *input_path,
                            const QwAppOptions *options,
                            uint8_t **out_pdf, size_t *out_size,
                            QwConvertReport *report)
{
    QwCadDocument *document = NULL;
    QwCadImage image;
    QwRasterPage page;
    uint8_t *rgb = NULL;
    size_t pixel_count;
    size_t index;
    uint32_t rendered_width = 0u;
    uint32_t rendered_height = 0u;
    int rc;
    (void)options;
    if (!out_pdf || !out_size) return QW_STATUS_ERR_INVALID_ARGUMENT;
    *out_pdf = NULL;
    *out_size = 0u;
    if (cad_extension(input_path) == 0) return QW_STATUS_ERR_UNSUPPORTED;
    rc = cad_parse_file(input_path, &document, report);
    if (rc != QW_STATUS_OK) return rc;
    memset(&image, 0, sizeof(image));
    if (qw_cad_render_rgba(document, QW_CAD_ROUTE_WIDTH, &image) != QW_CAD_OK) {
        qw_cad_document_free(document);
        return QW_STATUS_ERR_DECODE;
    }
    rendered_width = image.width;
    rendered_height = image.height;
    pixel_count = (size_t)image.width * image.height;
    if (pixel_count > (size_t)20000000) {
        qw_cad_image_free(&image);
        qw_cad_document_free(document);
        return QW_STATUS_ERR_RESOURCE_LIMIT;
    }
    rgb = (uint8_t *)malloc(pixel_count * 3u);
    if (!rgb) {
        qw_cad_image_free(&image);
        qw_cad_document_free(document);
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    for (index = 0u; index < pixel_count; ++index) {
        rgb[index * 3u] = image.pixels[index * 4u];
        rgb[index * 3u + 1u] = image.pixels[index * 4u + 1u];
        rgb[index * 3u + 2u] = image.pixels[index * 4u + 2u];
    }
    page.pixels = rgb;
    page.stride = (size_t)image.width * 3u;
    page.width = image.width;
    page.height = image.height;
    page.channels = 3;
    rc = qw_raster_pages_to_pdf_mode(&page, 1u, QW_RASTER_PAGE_MODE_A4,
                                     out_pdf, out_size, report);
    free(rgb);
    qw_cad_image_free(&image);
    qw_cad_document_free(document);
    if (rc == QW_STATUS_OK && report) {
        report->pages_written = 1u;
        report->format = QW_FORMAT_UNKNOWN;
        snprintf(report->note, sizeof(report->note),
                 "CAD rasterised at %ux%u; text glyphs are placeholder bars",
                 rendered_width, rendered_height);
    }
    return rc;
}




