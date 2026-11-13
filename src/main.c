#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#if defined(QUIREWISE_LINK_DOCUMENT)
#include <quirewise/convert.h>
#include <quirewise/status.h>
#endif

#include "app_options.h"

#if defined(QUIREWISE_APP_PAGE_ROUTES)
#include "page_routes.h"
#endif

#if defined(QUIREWISE_APP_SUBTITLE_ROUTES)
#include "subtitle_routes.h"
#endif

#if defined(QUIREWISE_APP_AUDIO_CHECK)
#include "audio_check.h"
#endif

#if defined(QUIREWISE_APP_DATA_ROUTES)
#include "data_routes.h"
#endif

#if defined(QUIREWISE_APP_COMIC_ROUTES)
#include "comic_routes.h"
#endif

#if defined(QUIREWISE_APP_CAD_ROUTES)
#include "cad_routes.h"
#endif

static void print_version(void)
{
    puts("Quirewise application 0.1.0");
}

static void print_help(const char *name)
{
    printf("Quirewise application shell\n\n");
    printf("Usage: %s INPUT [INPUT ...] [options]\n", name);
    printf("       %s --version | --libraries | --help\n\n", name);
    printf("Convert one or more inputs to an output format. Existing outputs\n");
    printf("are never overwritten. Without -o the input name is reused with\n");
    printf("the target extension.\n\n");
    printf("Options:\n");
    printf("  -o, --out FILE       write the conversion result to FILE\n");
    printf("      --out-dir DIR    put default output names under DIR\n");
    printf("      --to FORMAT      target format: pdf (default), txt, png\n");
    printf("      --check          verify inputs can be read; writes nothing\n");
    printf("      --quiet          suppress success output\n");
    printf("      --page MODE      raster page box: image (default) or a4\n");
    printf("      --pages RULE     PDG page rule: auto, body, body+att, all\n");
    printf("      --archive-password TEXT  CBZ archive password\n");
    printf("      --audio-track N  one-based audio track for --check\n");
    printf("      --help           show this help\n");
    printf("      --version        show the application version\n");
    printf("      --libraries      list the libraries selected at configure time\n");
    printf("\nThe application consumes independent Quirewise libraries installed\n");
    printf("as CMake packages.\n");
}

static void print_libraries(void)
{
    puts("Independent library composition is selected at CMake configure time.");
#ifdef QUIREWISE_LINK_RUNTIME
    puts("  runtime");
#endif
#ifdef QUIREWISE_LINK_IMAGE
    puts("  image");
#endif
#ifdef QUIREWISE_LINK_ARCHIVE
    puts("  archive");
#endif
#ifdef QUIREWISE_LINK_PAGE
    puts("  page");
#endif
#ifdef QUIREWISE_LINK_PDG
    puts("  pdg");
#endif
#ifdef QUIREWISE_LINK_DOCUMENT
    puts("  document");
#endif
#ifdef QUIREWISE_LINK_EBOOK
    puts("  ebook");
#endif
#ifdef QUIREWISE_LINK_TEXT
    puts("  text");
#endif
#ifdef QUIREWISE_LINK_DATA
    puts("  data");
#endif
#ifdef QUIREWISE_LINK_SPREADSHEET
    puts("  spreadsheet");
#endif
#ifdef QUIREWISE_LINK_AUDIO
    puts("  audio");
#endif
#ifdef QUIREWISE_LINK_SUBTITLE
    puts("  subtitle");
#endif
#ifdef QUIREWISE_LINK_VECTOR
    puts("  vector");
#endif
#ifdef QUIREWISE_LINK_COMIC
    puts("  comic");
#endif
}

#if defined(QUIREWISE_LINK_DOCUMENT)

typedef struct CliTarget {
    const char *name;
    QwOutputFormat format;
    const char *extension;
} CliTarget;

static const CliTarget cli_targets[] = {
    { "pdf", QW_FORMAT_PDF, "pdf" },
    { "txt", QW_FORMAT_TXT, "txt" },
    { "text", QW_FORMAT_TXT, "txt" },
    { "png", QW_FORMAT_PNG, "png" }
};

static int cli_name_equals(const char *left, const char *right)
{
    size_t index = 0u;
    if (!left || !right) return 0;
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

static const CliTarget *cli_find_target(const char *name)
{
    size_t index;
    for (index = 0u; index < sizeof(cli_targets) / sizeof(cli_targets[0]);
         ++index) {
        if (cli_name_equals(name, cli_targets[index].name))
            return &cli_targets[index];
    }
    return NULL;
}

static char *cli_default_output(const char *input, const char *extension,
                                const char *out_dir)
{
    const char *base = input;
    const char *dot;
    size_t directory_length = 0u;
    size_t stem_length;
    size_t extension_length;
    size_t index;
    char *output;

    if (!input || !extension) return NULL;
    for (index = 0u; input[index]; ++index) {
        if (input[index] == '/' || input[index] == '\\')
            directory_length = index + 1u;
    }
    base = input + directory_length;
    dot = strrchr(base, '.');
    stem_length = (dot && dot != base) ? (size_t)(dot - base) : strlen(base);
    extension_length = strlen(extension);
    if (out_dir) {
        size_t out_length = strlen(out_dir);
        int separator = out_length > 0u &&
                        out_dir[out_length - 1u] != '/' &&
                        out_dir[out_length - 1u] != '\\';
        output = (char *)malloc(out_length + (size_t)separator + stem_length +
                                1u + extension_length + 2u);
        if (!output) return NULL;
        memcpy(output, out_dir, out_length);
        if (separator) output[out_length++] = '/';
        memcpy(output + out_length, base, stem_length);
        output[out_length + stem_length] = '.';
        memcpy(output + out_length + stem_length + 1u, extension,
               extension_length + 1u);
        return output;
    }
    output = (char *)malloc(directory_length + stem_length + 1u +
                            extension_length + 1u);
    if (!output) return NULL;
    memcpy(output, input, directory_length);
    memcpy(output + directory_length, base, stem_length);
    output[directory_length + stem_length] = '.';
    memcpy(output + directory_length + stem_length + 1u, extension,
           extension_length + 1u);
    return output;
}

static const char *cli_status_text(int status)
{
    switch (status) {
    case QW_STATUS_OK: return "ok";
    case QW_STATUS_ERR_INVALID_ARGUMENT: return "invalid argument";
    case QW_STATUS_ERR_OUT_OF_MEMORY: return "out of memory";
    case QW_STATUS_ERR_IO: return "I/O error";
    case QW_STATUS_ERR_FORMAT: return "format error";
    case QW_STATUS_ERR_UNSUPPORTED: return "unsupported";
    case QW_STATUS_ERR_DECODE: return "decode error";
    case QW_STATUS_ERR_EMPTY: return "empty input";
    case QW_STATUS_ERR_EXTERNAL_DECODER_REQUIRED:
        return "external decoder required";
    case QW_STATUS_ERR_RESOURCE_LIMIT: return "resource limit";
    default: return "conversion failed";
    }
}

static int cli_path_exists(const char *path)
{
    FILE *file = fopen(path, "rb");
    if (!file) return 0;
    fclose(file);
    return 1;
}

static int cli_write_pdf(const char *path, const uint8_t *data, size_t size,
                         QwConvertReport *report)
{
    FILE *file;
    if (cli_path_exists(path)) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "output already exists and is never overwritten");
        return QW_STATUS_ERR_IO;
    }
    file = fopen(path, "wb");
    if (!file) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "cannot create output file");
        return QW_STATUS_ERR_IO;
    }
    if (size > 0 && fwrite(data, 1u, size, file) != size) {
        fclose(file);
        remove(path);
        if (report) snprintf(report->note, sizeof(report->note),
                             "short write to output file");
        return QW_STATUS_ERR_IO;
    }
    if (fclose(file) != 0) {
        remove(path);
        return QW_STATUS_ERR_IO;
    }
    return QW_STATUS_OK;
}

static int cli_run(const char *input, const char *output,
                   const char *target_name, int check, const char *out_dir,
                   int quiet, const QwAppOptions *app_options)
{
    const CliTarget *target = NULL;
    QwConvertOptions options = QW_CONVERT_OPTIONS_INIT;
    QwConvertReport report;
    char *default_output = NULL;
    const char *final_output = output;
    int status;

    if (!check) {
        target = target_name ? cli_find_target(target_name)
                             : cli_find_target("pdf");
        if (!target) {
            fprintf(stderr, "error: unsupported target format '%s'\n",
                    target_name ? target_name : "");
            fprintf(stderr, "supported targets: pdf, txt, png\n");
            return 2;
        }
        if (!final_output) {
            default_output = cli_default_output(input, target->extension,
                                                out_dir);
            if (!default_output) {
                fprintf(stderr, "error: out of memory\n");
                return 1;
            }
            final_output = default_output;
        }
    } else if (target_name) {
        fprintf(stderr, "error: --to cannot be combined with --check\n");
        return 2;
    }

    memset(&report, 0, sizeof(report));
    if (check) {
        status = qw_check_file(input, &options, &report);
#if defined(QUIREWISE_APP_PAGE_ROUTES)
        if (status != QW_STATUS_OK) {
            QwConvertReport page_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&page_report, 0, sizeof(page_report));
            if (qw_app_page_convert_file(input, app_options, &pdf, &pdf_size,
                                         &page_report) == QW_STATUS_OK) {
                qw_buffer_free(pdf);
                status = QW_STATUS_OK;
                report = page_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_SUBTITLE_ROUTES)
        if (status != QW_STATUS_OK) {
            QwConvertReport subtitle_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&subtitle_report, 0, sizeof(subtitle_report));
            if (qw_app_subtitle_convert_file(input, &pdf, &pdf_size,
                                             &subtitle_report) ==
                QW_STATUS_OK) {
                qw_buffer_free(pdf);
                status = QW_STATUS_OK;
                report = subtitle_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_COMIC_ROUTES)
        if (status != QW_STATUS_OK) {
            QwConvertReport comic_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&comic_report, 0, sizeof(comic_report));
            if (qw_app_comic_convert_file(input, app_options, &pdf, &pdf_size,
                                          &comic_report) == QW_STATUS_OK) {
                qw_buffer_free(pdf);
                status = QW_STATUS_OK;
                report = comic_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_DATA_ROUTES)
        if (status != QW_STATUS_OK) {
            QwConvertReport data_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&data_report, 0, sizeof(data_report));
            if (qw_app_data_convert_file(input, &pdf, &pdf_size,
                                         &data_report) == QW_STATUS_OK) {
                qw_buffer_free(pdf);
                status = QW_STATUS_OK;
                report = data_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_CAD_ROUTES)
        if (status != QW_STATUS_OK) {
            QwConvertReport cad_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&cad_report, 0, sizeof(cad_report));
            if (qw_app_cad_check_file(input, &cad_report) == QW_STATUS_OK) {
                status = QW_STATUS_OK;
                report = cad_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_AUDIO_CHECK)
        if (status != QW_STATUS_OK) {
            QwConvertReport audio_report;
            memset(&audio_report, 0, sizeof(audio_report));
            if (qw_app_audio_check_file(input, app_options->audio_track,
                                        &audio_report) == QW_STATUS_OK) {
                status = QW_STATUS_OK;
                report = audio_report;
            }
        }
#endif
    } else {
        status = qw_convert_file_to_format(input, final_output, target->format,
                                           &options, &report);
#if defined(QUIREWISE_APP_PAGE_ROUTES)
        if (status != QW_STATUS_OK && target->format == QW_FORMAT_PDF) {
            QwConvertReport page_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&page_report, 0, sizeof(page_report));
            if (qw_app_page_convert_file(input, app_options, &pdf, &pdf_size,
                                         &page_report) == QW_STATUS_OK) {
                status = cli_write_pdf(final_output, pdf, pdf_size,
                                       &page_report);
                qw_buffer_free(pdf);
                if (status == QW_STATUS_OK) report = page_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_SUBTITLE_ROUTES)
        if (status != QW_STATUS_OK && target->format == QW_FORMAT_PDF) {
            QwConvertReport subtitle_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&subtitle_report, 0, sizeof(subtitle_report));
            if (qw_app_subtitle_convert_file(input, &pdf, &pdf_size,
                                             &subtitle_report) ==
                QW_STATUS_OK) {
                status = cli_write_pdf(final_output, pdf, pdf_size,
                                       &subtitle_report);
                qw_buffer_free(pdf);
                if (status == QW_STATUS_OK) report = subtitle_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_COMIC_ROUTES)
        if (status != QW_STATUS_OK && target->format == QW_FORMAT_PDF) {
            QwConvertReport comic_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&comic_report, 0, sizeof(comic_report));
            if (qw_app_comic_convert_file(input, app_options, &pdf, &pdf_size,
                                          &comic_report) == QW_STATUS_OK) {
                status = cli_write_pdf(final_output, pdf, pdf_size,
                                       &comic_report);
                qw_buffer_free(pdf);
                if (status == QW_STATUS_OK) report = comic_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_DATA_ROUTES)
        if (status != QW_STATUS_OK && target->format == QW_FORMAT_PDF) {
            QwConvertReport data_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&data_report, 0, sizeof(data_report));
            if (qw_app_data_convert_file(input, &pdf, &pdf_size,
                                         &data_report) == QW_STATUS_OK) {
                status = cli_write_pdf(final_output, pdf, pdf_size,
                                       &data_report);
                qw_buffer_free(pdf);
                if (status == QW_STATUS_OK) report = data_report;
            }
        }
#endif
#if defined(QUIREWISE_APP_CAD_ROUTES)
        if (status != QW_STATUS_OK && target->format == QW_FORMAT_PDF) {
            QwConvertReport cad_report;
            uint8_t *pdf = NULL;
            size_t pdf_size = 0u;
            memset(&cad_report, 0, sizeof(cad_report));
            if (qw_app_cad_convert_file(input, app_options, &pdf, &pdf_size,
                                        &cad_report) == QW_STATUS_OK) {
                status = cli_write_pdf(final_output, pdf, pdf_size,
                                       &cad_report);
                qw_buffer_free(pdf);
                if (status == QW_STATUS_OK) report = cad_report;
            }
        }
        if (status != QW_STATUS_OK && target->format == QW_FORMAT_TXT) {
            QwConvertReport cad_report;
            uint8_t *text = NULL;
            size_t text_size = 0u;
            memset(&cad_report, 0, sizeof(cad_report));
            if (qw_app_cad_extract_text(input, &text, &text_size,
                                        &cad_report) == QW_STATUS_OK) {
                status = cli_write_pdf(final_output, text, text_size,
                                       &cad_report);
                qw_buffer_free(text);
                if (status == QW_STATUS_OK) report = cad_report;
            }
        }
#endif
    }

    if (status == QW_STATUS_OK && report.skipped_pages > 0u) {
        if (check) {
            /* --check must fail when part of the input could not be read. */
            status = QW_STATUS_ERR_UNSUPPORTED;
            if (!report.note[0]) {
                snprintf(report.note, sizeof(report.note),
                         "%zu page(s) could not be read", report.skipped_pages);
            }
        } else {
            fprintf(stderr, "warning: %zu page(s) skipped",
                    report.skipped_pages);
            if (report.note[0]) fprintf(stderr, ": %s", report.note);
            fprintf(stderr, "\n");
        }
    }

    if (status == QW_STATUS_OK) {
        if (!quiet) {
            if (check) {
                printf("OK\n");
            } else {
                printf("%s\n", final_output);
            }
        }
        free(default_output);
        return 0;
    }

    fprintf(stderr, "error: %s", cli_status_text(status));
    if (report.note[0]) fprintf(stderr, ": %s", report.note);
    fprintf(stderr, "\n");
    free(default_output);
    return 1;
}

#endif /* QUIREWISE_LINK_DOCUMENT */

static int cli_arg_equals(const char *left, const char *right)
{
    size_t index = 0u;
    if (!left || !right) return 0;
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

static int cli_parse_page_mode(const char *text, int *out)
{
    if (cli_arg_equals(text, "a4")) {
        *out = 0; /* QW_RASTER_PAGE_MODE_A4 */
        return 1;
    }
    if (cli_arg_equals(text, "image")) {
        *out = 1; /* QW_RASTER_PAGE_MODE_IMAGE */
        return 1;
    }
    return 0;
}

static int cli_parse_page_rule(const char *text, int *out)
{
    if (cli_arg_equals(text, "auto")) { *out = 0; return 1; }
    if (cli_arg_equals(text, "body")) { *out = 1; return 1; }
    if (cli_arg_equals(text, "body+att") || cli_arg_equals(text, "body-att")) {
        *out = 2;
        return 1;
    }
    if (cli_arg_equals(text, "all")) { *out = 3; return 1; }
    return 0;
}

static int cli_parse_track(const char *text, size_t *out)
{
    size_t value = 0u;
    size_t index;
    if (!text || !text[0]) return 0;
    for (index = 0u; text[index]; ++index) {
        if (text[index] < '0' || text[index] > '9') return 0;
        value = value * 10u + (size_t)(text[index] - '0');
        if (value > 100000u) return 0;
    }
    *out = value;
    return 1;
}

int main(int argc, char **argv)
{
    const char *inputs[64];
    int input_count = 0;
    const char *output = NULL;
    const char *out_dir = NULL;
    const char *target_name = NULL;
    QwAppOptions app_options = { 1, 0, NULL, 0u };
    int check = 0;
    int quiet = 0;
    int index;
    int overall = 0;

    if (argc <= 1) {
        print_help(argv[0]);
        return 0;
    }

    for (index = 1; index < argc; ++index) {
        const char *argument = argv[index];
        if (strcmp(argument, "--help") == 0 || strcmp(argument, "-h") == 0) {
            print_help(argv[0]);
            return 0;
        }
        if (strcmp(argument, "--version") == 0 || strcmp(argument, "-V") == 0) {
            print_version();
            return 0;
        }
        if (strcmp(argument, "--libraries") == 0) {
            print_libraries();
            return 0;
        }
        if (strcmp(argument, "--check") == 0) {
            check = 1;
            continue;
        }
        if (strcmp(argument, "--quiet") == 0) {
            quiet = 1;
            continue;
        }
        if (strcmp(argument, "--to") == 0) {
            if (index + 1 >= argc) {
                fprintf(stderr, "error: --to requires a format name\n");
                return 2;
            }
            target_name = argv[++index];
            continue;
        }
        if (strcmp(argument, "-o") == 0 || strcmp(argument, "--out") == 0) {
            if (index + 1 >= argc) {
                fprintf(stderr, "error: %s requires a file name\n", argument);
                return 2;
            }
            output = argv[++index];
            continue;
        }
        if (strcmp(argument, "--out-dir") == 0) {
            if (index + 1 >= argc) {
                fprintf(stderr, "error: --out-dir requires a directory\n");
                return 2;
            }
            out_dir = argv[++index];
            continue;
        }
        if (strcmp(argument, "--page") == 0) {
            if (index + 1 >= argc ||
                !cli_parse_page_mode(argv[index + 1],
                                     &app_options.raster_page_mode)) {
                fprintf(stderr, "error: --page expects image or a4\n");
                return 2;
            }
            ++index;
            continue;
        }
        if (strcmp(argument, "--pages") == 0) {
            if (index + 1 >= argc ||
                !cli_parse_page_rule(argv[index + 1],
                                     &app_options.pdz_page_rule)) {
                fprintf(stderr,
                        "error: --pages expects auto, body, body+att or all\n");
                return 2;
            }
            ++index;
            continue;
        }
        if (strcmp(argument, "--archive-password") == 0 ||
            strcmp(argument, "--zip-password") == 0) {
            if (index + 1 >= argc) {
                fprintf(stderr, "error: %s requires text\n", argument);
                return 2;
            }
            app_options.archive_password = argv[++index];
            continue;
        }
        if (strcmp(argument, "--audio-track") == 0) {
            if (index + 1 >= argc ||
                !cli_parse_track(argv[index + 1],
                                 &app_options.audio_track)) {
                fprintf(stderr, "error: --audio-track expects a number\n");
                return 2;
            }
            ++index;
            continue;
        }
        if (argument[0] == '-' && argument[1] != '\0') {
            fprintf(stderr, "error: unknown option '%s'\n", argument);
            return 2;
        }
        if (input_count >= (int)(sizeof(inputs) / sizeof(inputs[0]))) {
            fprintf(stderr, "error: too many input files\n");
            return 2;
        }
        inputs[input_count++] = argument;
    }

    if (input_count == 0) {
        fprintf(stderr, "error: missing input file\n");
        print_help(argv[0]);
        return 2;
    }
    if (output && input_count > 1) {
        fprintf(stderr, "error: -o cannot be used with multiple inputs\n");
        return 2;
    }
    if (check && output) {
        fprintf(stderr, "error: -o cannot be combined with --check\n");
        return 2;
    }

#if defined(QUIREWISE_LINK_DOCUMENT)
    for (index = 0; index < input_count; ++index) {
        int rc = cli_run(inputs[index], output, target_name, check, out_dir,
                         quiet, &app_options);
        if (rc == 2) return 2;
        if (rc != 0) overall = 1;
    }
    return overall;
#else
    (void)app_options;
    (void)out_dir;
    (void)quiet;
    (void)check;
    (void)target_name;
    (void)inputs;
    (void)output;
    fprintf(stderr,
            "error: this build does not link quirewise-document; "
            "conversions are unavailable\n");
    return 2;
#endif
}
