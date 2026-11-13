#include "svg_routes.h"
#include "app_file.h"

#include <quirewise/convert.h>
#include <quirewise/svg.h>
#include <quirewise/svgz.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define QW_SVG_ROUTE_MAX_INPUT (32u * 1024u * 1024u)

static int svg_extension(const char *path, int *out_compressed)
{
    const char *dot = strrchr(path, '.');
    if (!dot) return 0;
    ++dot;
    if ((dot[0] == 's' || dot[0] == 'S') &&
        (dot[1] == 'v' || dot[1] == 'V') &&
        (dot[2] == 'g' || dot[2] == 'G')) {
        if (dot[3] == '\0') {
            *out_compressed = 0;
            return 1;
        }
        if ((dot[3] == 'z' || dot[3] == 'Z') && dot[4] == '\0') {
            *out_compressed = 1;
            return 1;
        }
    }
    return 0;
}

static int svg_status_to_qw(QwSvgStatus status)
{
    switch (status) {
    case QW_SVG_OK: return QW_STATUS_OK;
    case QW_SVG_ERR_INVALID_ARGUMENT: return QW_STATUS_ERR_INVALID_ARGUMENT;
    case QW_SVG_ERR_OUT_OF_MEMORY: return QW_STATUS_ERR_OUT_OF_MEMORY;
    case QW_SVG_ERR_FORMAT: return QW_STATUS_ERR_FORMAT;
    case QW_SVG_ERR_UNSUPPORTED: return QW_STATUS_ERR_UNSUPPORTED;
    case QW_SVG_ERR_RESOURCE_LIMIT: return QW_STATUS_ERR_RESOURCE_LIMIT;
    default: return QW_STATUS_ERR_DECODE;
    }
}

static int svgz_status_to_qw(QwSvgzStatus status)
{
    switch (status) {
    case QW_SVGZ_OK: return QW_STATUS_OK;
    case QW_SVGZ_ERR_INVALID_ARGUMENT:
        return QW_STATUS_ERR_INVALID_ARGUMENT;
    case QW_SVGZ_ERR_OUT_OF_MEMORY: return QW_STATUS_ERR_OUT_OF_MEMORY;
    case QW_SVGZ_ERR_FORMAT: return QW_STATUS_ERR_FORMAT;
    case QW_SVGZ_ERR_RESOURCE_LIMIT: return QW_STATUS_ERR_RESOURCE_LIMIT;
    case QW_SVGZ_ERR_DECODE: return QW_STATUS_ERR_DECODE;
    default: return QW_STATUS_ERR_DECODE;
    }
}

static int svg_read_file(const char *path, uint8_t **out_data,
                         size_t *out_size)
{
    FILE *file;
    long length;
    uint8_t *data;

    file = qw_app_fopen_utf8(path, "rb");
    if (!file) return QW_STATUS_ERR_IO;
    if (fseek(file, 0, SEEK_END) != 0) {
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    length = ftell(file);
    if (length < 0) {
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    if ((unsigned long)length > (unsigned long)QW_SVG_ROUTE_MAX_INPUT) {
        fclose(file);
        return QW_STATUS_ERR_RESOURCE_LIMIT;
    }
    if (fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return QW_STATUS_ERR_IO;
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
    *out_data = data;
    *out_size = (size_t)length;
    return QW_STATUS_OK;
}

int qw_app_svg_convert_file(const char *path, const QwAppOptions *options,
                            uint8_t **out_pdf, size_t *out_size,
                            QwConvertReport *report)
{
    static const QwAppOptions defaults = {
        QW_RASTER_PAGE_MODE_IMAGE, 0, NULL, 0u
    };
    uint8_t *data = NULL;
    size_t size = 0u;
    uint8_t *rgb = NULL;
    size_t rgb_size;
    int compressed = 0;
    const uint8_t *svg_bytes;
    size_t svg_size;
    QwSvgzDocument svgz;
    QwSvgImage image;
    QwSvgError svg_error;
    QwRasterPage page;
    int rc;
    size_t row;
    size_t column;

    if (!path || !out_pdf || !out_size) return QW_STATUS_ERR_INVALID_ARGUMENT;
    if (!options) options = &defaults;
    *out_pdf = NULL;
    *out_size = 0u;
    if (!svg_extension(path, &compressed)) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "only .svg/.svgz inputs are supported");
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    rc = svg_read_file(path, &data, &size);
    if (rc != QW_STATUS_OK) return rc;

    memset(&svgz, 0, sizeof(svgz));
    if (compressed) {
        QwSvgzStatus status = qw_svgz_decode(data, size, &svgz);
        if (status != QW_SVGZ_OK) {
            if (report) snprintf(report->note, sizeof(report->note),
                                 "SVGZ decompression failed: %s",
                                 qw_svgz_status_string(status));
            free(data);
            return svgz_status_to_qw(status);
        }
        svg_bytes = svgz.svg_utf8;
        svg_size = svgz.svg_size;
    } else {
        svg_bytes = data;
        svg_size = size;
    }

    memset(&image, 0, sizeof(image));
    memset(&svg_error, 0, sizeof(svg_error));
    {
        QwSvgStatus status = qw_svg_decode(svg_bytes, svg_size, &image,
                                           &svg_error);
        if (svgz.svg_utf8) qw_svgz_document_free(&svgz);
        free(data);
        if (status != QW_SVG_OK) {
            if (report) snprintf(report->note, sizeof(report->note),
                                 "SVG render failed: %s",
                                 svg_error.message[0]
                                     ? svg_error.message
                                     : qw_svg_status_string(status));
            return svg_status_to_qw(status);
        }
    }
    if (!image.pixels || !image.width || !image.height ||
        image.stride < (size_t)image.width * 4u) {
        qw_svg_image_free(&image);
        if (report) snprintf(report->note, sizeof(report->note),
                             "SVG renderer produced an invalid image");
        return QW_STATUS_ERR_FORMAT;
    }

    rgb_size = (size_t)image.width * (size_t)image.height * 3u;
    rgb = (uint8_t *)malloc(rgb_size ? rgb_size : 1u);
    if (!rgb) {
        qw_svg_image_free(&image);
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    for (row = 0u; row < image.height; ++row) {
        const uint8_t *src = image.pixels + row * image.stride;
        uint8_t *dst = rgb + row * (size_t)image.width * 3u;
        for (column = 0u; column < image.width; ++column) {
            unsigned alpha = src[column * 4u + 3u];
            unsigned red = src[column * 4u + 0u];
            unsigned green = src[column * 4u + 1u];
            unsigned blue = src[column * 4u + 2u];
            /* Compose over white, matching the other raster routes. */
            dst[column * 3u + 0u] =
                (uint8_t)((red * alpha + 255u * (255u - alpha)) / 255u);
            dst[column * 3u + 1u] =
                (uint8_t)((green * alpha + 255u * (255u - alpha)) / 255u);
            dst[column * 3u + 2u] =
                (uint8_t)((blue * alpha + 255u * (255u - alpha)) / 255u);
        }
    }
    memset(&page, 0, sizeof(page));
    page.pixels = rgb;
    page.stride = (size_t)image.width * 3u;
    page.width = image.width;
    page.height = image.height;
    page.channels = 3;
    rc = qw_raster_pages_to_pdf_mode(&page, 1u, options->raster_page_mode,
                                     out_pdf, out_size, report);
    free(rgb);
    qw_svg_image_free(&image);
    if (rc == QW_STATUS_OK && report) {
        snprintf(report->note, sizeof(report->note),
                 "SVG subset rendered to a %ux%u raster page; vector "
                 "structure, links, animation and metadata are not preserved "
                 "(QW_ROUTE_LOSS_RASTERIZATION)",
                 (unsigned)page.width, (unsigned)page.height);
        report->pages_written = 1u;
        report->output_size = *out_size;
    }
    return rc;
}

int qw_app_svg_check_file(const char *path, QwConvertReport *report)
{
    uint8_t *pdf = NULL;
    size_t pdf_size = 0u;
    int rc = qw_app_svg_convert_file(path, NULL, &pdf, &pdf_size, report);
    qw_buffer_free(pdf);
    return rc;
}
