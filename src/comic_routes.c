#include "comic_routes.h"

#include <quirewise/comic.h>
#include <quirewise/image.h>
#include <quirewise/status.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define QW_COMIC_ROUTE_MAX_INPUT (512u * 1024u * 1024u)

static int comic_iequals(const char *left, const char *right)
{
    size_t index = 0u;
    while (left[index] && right[index]) {
        char a = left[index];
        char b = right[index];
        if (a >= 'A' && a <= 'Z') a = (char)(a - 'A' + 'a');
        if (b >= 'A' && b <= 'Z') b = (char)(b - 'A' + 'a');
        if (a != b) return 0;
        ++index;
    }
    return left[index] == '\0' && right[index] == '\0';
}

static int comic_extension_format(const char *path,
                                  QwComicArchiveFormat *out)
{
    const char *dot = strrchr(path, '.');
    if (!dot) return 0;
    ++dot;
    if (comic_iequals(dot, "cbz")) {
        *out = QW_COMIC_ARCHIVE_ZIP;
    } else if (comic_iequals(dot, "cbt")) {
        *out = QW_COMIC_ARCHIVE_USTAR;
    } else {
        return 0;
    }
    return 1;
}

int qw_app_comic_convert_file(const char *path,
                              uint8_t **out_pdf, size_t *out_size,
                              QwConvertReport *report)
{
    QwComicArchiveFormat format;
    QwComicArchive *archive = NULL;
    QwComicStatus status;
    QwImage *images = NULL;
    QwRasterPage *pages = NULL;
    FILE *file;
    long length;
    uint8_t *data;
    size_t page_count;
    size_t page_index;
    size_t decoded = 0u;
    int rc;

    if (!path || !out_pdf || !out_size) return QW_STATUS_ERR_INVALID_ARGUMENT;
    *out_pdf = NULL;
    *out_size = 0u;
    if (!comic_extension_format(path, &format)) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "only CBZ/CBT comic archives are supported");
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    file = fopen(path, "rb");
    if (!file) return QW_STATUS_ERR_IO;
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    if ((unsigned long)length > (unsigned long)QW_COMIC_ROUTE_MAX_INPUT) {
        fclose(file);
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

    status = qw_comic_archive_open(data, (size_t)length, format, NULL,
                                   &archive);
    if (status != QW_COMIC_OK || !archive) {
        free(data);
        if (report) snprintf(report->note, sizeof(report->note),
                             "comic archive open failed with status %d",
                             (int)status);
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    page_count = qw_comic_archive_page_count(archive);
    if (page_count == 0u) {
        qw_comic_archive_close(archive);
        free(data);
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    images = (QwImage *)calloc(page_count, sizeof(QwImage));
    pages = (QwRasterPage *)calloc(page_count, sizeof(QwRasterPage));
    if (!images || !pages) {
        free(images);
        free(pages);
        qw_comic_archive_close(archive);
        free(data);
        return QW_STATUS_ERR_OUT_OF_MEMORY;
    }
    for (page_index = 0u; page_index < page_count; ++page_index) {
        QwComicPageInfo info;
        uint8_t *page_data = NULL;
        size_t page_size = 0u;
        QwImage image;
        memset(&info, 0, sizeof(info));
        if (qw_comic_archive_page_info(archive, page_index, &info) ==
                QW_COMIC_OK &&
            info.is_empty)
            continue;
        status = qw_comic_archive_read_page(archive, page_index, &page_data,
                                            &page_size);
        if (status != QW_COMIC_OK || !page_data) continue;
        memset(&image, 0, sizeof(image));
        {
            int image_status = qw_image_decode(page_data, page_size, &image);
            qw_comic_page_data_free(page_data);
            if (image_status != QW_IMAGE_OK) continue;
        }
        images[decoded] = image;
        pages[decoded].pixels = image.pixels;
        pages[decoded].stride = image.stride;
        pages[decoded].width = image.width;
        pages[decoded].height = image.height;
        pages[decoded].channels =
            image.format == QW_IMAGE_PIXEL_RGB24 ? 3 : 1;
        ++decoded;
    }
    qw_comic_archive_close(archive);
    free(data);
    if (decoded == 0u) {
        free(images);
        free(pages);
        if (report) snprintf(report->note, sizeof(report->note),
                             "comic archive contains no decodable image pages");
        return QW_STATUS_ERR_UNSUPPORTED;
    }
    rc = qw_raster_pages_to_pdf(pages, decoded, out_pdf, out_size, report);
    for (page_index = 0u; page_index < decoded; ++page_index)
        qw_image_free(&images[page_index]);
    free(images);
    free(pages);
    if (rc == QW_STATUS_OK && report) {
        snprintf(report->note, sizeof(report->note),
                 "comic archive: %zu image page(s) rendered", decoded);
    }
    return rc;
}
