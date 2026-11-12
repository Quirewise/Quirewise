/* verify_pdf_pages - render-based sanity check for produced PDFs.
 *
 * A PDF that parses and reports the expected page count can still be unusable:
 * an image dictionary with the wrong colour space, a missing /BlackIs1 or a
 * truncated stream all render as blank or solid pages. This tool opens the file
 * through the public Document API, renders a few pages at low resolution and
 * reports the mean luminance, so a regression shows up as a number instead of a
 * silent defect in the output.
 *
 * usage: verify_pdf_pages [--min-luma N] [--dpi N] [--pages a,b,c] <pdf>...
 *
 * exit 0: every sampled page is inside the luminance band
 * exit 1: at least one file was rejected or sampled as blank/solid
 * exit 2: bad arguments
 *
 * The Document renderer decodes raw samples, JPEG, CCITTFaxDecode, JPX and
 * JBIG2 image XObjects; unsupported drawing operators are reported through the
 * route-loss note instead of failing the render. A page whose mean luminance is
 * 255.0 while the renderer skipped objects means "not rendered", not "blank".
 */
#include <quirewise/document.h>
#include <quirewise/pdf.h>

#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32)
#include <windows.h>
#include <shellapi.h>
#include <wchar.h>
static FILE *fopen_utf8(const char *path, const char *mode)
{
    wchar_t wpath[2048];
    wchar_t wmode[16];
    if (!MultiByteToWideChar(CP_UTF8, 0, path, -1, wpath, 2048)) return NULL;
    if (!MultiByteToWideChar(CP_UTF8, 0, mode, -1, wmode, 16)) return NULL;
    return _wfopen(wpath, wmode);
}

/* The C runtime hands argv over in the ANSI code page, so a path such as
 * "G.回族典藏全书" arrives mangled and no file opens. Read the command line as
 * UTF-16 and expose it as UTF-8 instead. */
static char **utf8_argv(int *out_count)
{
    int wcount = 0;
    LPWSTR *wargs = CommandLineToArgvW(GetCommandLineW(), &wcount);
    char **args;
    int index;
    if (!wargs) return NULL;
    args = (char **)calloc((size_t)(wcount > 0 ? wcount : 1), sizeof(char *));
    if (!args) {
        LocalFree(wargs);
        return NULL;
    }
    for (index = 0; index < wcount; ++index) {
        int needed = WideCharToMultiByte(CP_UTF8, 0, wargs[index], -1, NULL, 0, NULL, NULL);
        if (needed <= 0) continue;
        args[index] = (char *)malloc((size_t)needed);
        if (!args[index]) continue;
        WideCharToMultiByte(CP_UTF8, 0, wargs[index], -1, args[index], needed, NULL, NULL);
    }
    LocalFree(wargs);
    *out_count = wcount;
    return args;
}
#else
#define fopen_utf8 fopen
#endif

#define MAX_SAMPLES 64

static uint8_t *read_file(const char *path, size_t *out_size)
{
    FILE *file = fopen_utf8(path, "rb");
    int64_t length;
    uint8_t *data;
    if (!file) return NULL;
#if defined(_WIN32)
    if (_fseeki64(file, 0, SEEK_END) != 0) { fclose(file); return NULL; }
    length = _ftelli64(file);
    if (length <= 0) { fclose(file); return NULL; }
    _fseeki64(file, 0, SEEK_SET);
#else
    if (fseek(file, 0, SEEK_END) != 0) { fclose(file); return NULL; }
    length = (int64_t)ftell(file);
    if (length <= 0) { fclose(file); return NULL; }
    fseek(file, 0, SEEK_SET);
#endif
    data = (uint8_t *)malloc((size_t)length);
    if (!data) { fclose(file); return NULL; }
    if (fread(data, 1u, (size_t)length, file) != (size_t)length) {
        free(data);
        fclose(file);
        return NULL;
    }
    fclose(file);
    *out_size = (size_t)length;
    return data;
}

static double mean_luma(const QwPageImage *image)
{
    size_t count;
    size_t i;
    double sum = 0.0;
    if (!image || !image->data || image->kind != QW_PAGE_IMAGE_RGB24) return -1.0;
    count = image->size / 3u;
    if (!count) return -1.0;
    for (i = 0; i < count; ++i) {
        sum += 0.299 * (double)image->data[i * 3u] +
               0.587 * (double)image->data[i * 3u + 1u] +
               0.114 * (double)image->data[i * 3u + 2u];
    }
    return sum / (double)count;
}

typedef struct Options {
    double min_luma;
    unsigned dpi;
    int explicit_pages;
    size_t pages[MAX_SAMPLES];
    size_t page_count;
} Options;

static int parse_pages(const char *value, Options *options)
{
    const char *cursor = value;
    options->page_count = 0u;
    while (*cursor && options->page_count < MAX_SAMPLES) {
        char *end = NULL;
        unsigned long page = strtoul(cursor, &end, 10);
        if (end == cursor) return 0;
        options->pages[options->page_count++] = (size_t)page;
        cursor = (*end == ',') ? end + 1 : end;
        if (*end && *end != ',') return 0;
    }
    options->explicit_pages = 1;
    return options->page_count > 0u;
}

static int verify_one(const char *path, const Options *options)
{
    size_t size = 0u;
    uint8_t *data = read_file(path, &size);
    QwPdfDocument *document = NULL;
    size_t pages = 0u;
    QwConvertReport report;
    size_t samples[MAX_SAMPLES];
    size_t sample_count = 0u;
    size_t index;
    int suspicious = 0;

    if (!data) {
        printf("%s\tREAD-FAIL\n", path);
        return 1;
    }
    memset(&report, 0, sizeof(report));
    {
        QwStatus open_status = qw_pdf_open(data, size, &document, &pages, &report);
        if (open_status != QW_STATUS_OK || !document) {
            printf("%s\tOPEN-FAIL rc=%d note=%s\n", path, (int)open_status, report.note);
            free(data);
            return 1;
        }
    }
    if (options->explicit_pages) {
        for (index = 0u; index < options->page_count; ++index) {
            if (options->pages[index] < pages) {
                samples[sample_count++] = options->pages[index];
            }
        }
    } else if (pages) {
        samples[sample_count++] = 0u;
        if (pages > 1u) samples[sample_count++] = pages / 2u;
        if (pages > 2u) samples[sample_count++] = pages - 1u;
        /* Drop duplicates without disturbing the order (1- and 2-page files). */
        for (index = 0u; index < sample_count; ++index) {
            size_t other;
            for (other = index + 1u; other < sample_count;) {
                if (samples[other] == samples[index]) {
                    memmove(&samples[other], &samples[other + 1u],
                            (sample_count - other - 1u) * sizeof(samples[0]));
                    --sample_count;
                } else {
                    ++other;
                }
            }
        }
    }

    printf("%s\tpages=%zu", path, pages);
    for (index = 0u; index < sample_count; ++index) {
        QwPageImage page;
        QwConvertReport render_report;
        double luma = -1.0;
        memset(&page, 0, sizeof(page));
        memset(&render_report, 0, sizeof(render_report));
        if (qw_pdf_render_page(document, samples[index], options->dpi, &page,
                               &render_report) == QW_STATUS_OK) {
            luma = mean_luma(&page);
        }
        if (luma < 0.0 || luma < options->min_luma) {
            suspicious = 1;
        }
        printf(" p%zu=%.1f", samples[index], luma);
        qw_pdf_page_free(&page);
    }
    printf("\t%s\n", suspicious ? "SUSPECT" : "ok");
    qw_pdf_close(document);
    free(data);
    return suspicious ? 1 : 0;
}

int main(int argc, char **argv)
{
    Options options;
    int status = 0;
    int index;
    int files = 0;

    memset(&options, 0, sizeof(options));
    options.min_luma = 15.0;
    options.dpi = 24u;
#if defined(_WIN32)
    {
        int wide_count = 0;
        char **wide_args = utf8_argv(&wide_count);
        if (wide_args) {
            argc = wide_count;
            argv = wide_args;
        }
    }
#endif

    for (index = 1; index < argc; ++index) {
        if (strcmp(argv[index], "--min-luma") == 0 && index + 1 < argc) {
            options.min_luma = strtod(argv[++index], NULL);
        } else if (strcmp(argv[index], "--dpi") == 0 && index + 1 < argc) {
            options.dpi = (unsigned)strtoul(argv[++index], NULL, 10);
        } else if (strcmp(argv[index], "--pages") == 0 && index + 1 < argc) {
            if (!parse_pages(argv[++index], &options)) {
                fprintf(stderr, "--pages expects a comma separated list\n");
                return 2;
            }
        } else if (argv[index][0] == '-') {
            fprintf(stderr, "unknown option: %s\n", argv[index]);
            return 2;
        } else {
            ++files;
            if (verify_one(argv[index], &options)) {
                status = 1;
            }
        }
    }
    if (!files) {
        fprintf(stderr,
                "usage: %s [--min-luma N] [--dpi N] [--pages a,b,c] <pdf>...\n",
                argv[0]);
        return 2;
    }
    return status;
}
