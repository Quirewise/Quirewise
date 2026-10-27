#include <quirewise/archive.h>
#include <quirewise/audio.h>
#include <quirewise/data.h>
#include <quirewise/document.h>
#include <quirewise/image.h>
#include <quirewise/runtime.h>
#include <quirewise/spreadsheet.h>
#include <quirewise/subtitle.h>
#include <quirewise/svg.h>

#include <stdio.h>
#include <stdlib.h>

static int decode_image_path(const char *path)
{
    FILE *file;
    long length;
    uint8_t *data;
    QwImage image = {0};
    int status;

    file = fopen(path, "rb");
    if (!file) return 2;
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return 3;
    }
    data = (uint8_t *)malloc((size_t)length ? (size_t)length : 1u);
    if (!data || fread(data, 1u, (size_t)length, file) != (size_t)length) {
        free(data);
        fclose(file);
        return 4;
    }
    fclose(file);
    status = qw_image_decode(data, (size_t)length, &image);
    free(data);
    if (status != QW_IMAGE_OK) {
        fprintf(stderr, "image decode failed: %s\n",
                qw_image_status_string(status));
        return 5;
    }
    printf("decoded image: %ux%u (%zu bytes)\n",
           image.width, image.height, image.size);
    qw_image_free(&image);
    return 0;
}

int main(int argc, char **argv)
{
    puts("Quirewise consumer package smoke test");
    printf("runtime=%u image=%u archive=%u\n",
           (unsigned)qw_runtime_abi_version(),
           (unsigned)qw_image_abi_version(),
           (unsigned)qw_archive_abi_version());
    if (argc > 1) return decode_image_path(argv[1]);
    return 0;
}
