#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <quirewise/pipeline.h>

#include "app_options.h"

static void print_version(void)
{
#ifdef QUIREWISE_APP_VERSION
    puts("Quirewise application " QUIREWISE_APP_VERSION);
#else
    puts("Quirewise application 0.2.2");
#endif
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
    printf("      --to FORMAT      target: pdf (default), txt, png, json, jsonl,\n");
    printf("                       yaml, toml, xml, vcf, srt, vtt, lrc, sub,\n");
    printf("                       ass, ssa, sami, scc, ttml, csv, tsv, html, md, docx,\n");
    printf("                       epub, bmp, tiff, jpg, webp, tga, qoi, ppm,\n");
    printf("                       gif, hdr, sgi, pcx, htmlz, txtz, pmlz, xlsx, ods,\n");
    printf("                       opml, ipynb, hwpx\n");
    printf("      --check          verify inputs can be read; writes nothing\n");
    printf("      --quiet          suppress success output\n");
    printf("      --page MODE      raster page box: image (default) or a4\n");
    printf("      --pages RULE     PDG page rule: auto, body, body+att, all\n");
    printf("      --archive-password TEXT  CBZ archive password\n");
    printf("      --pdf-password TEXT      user password for encrypted PDF input\n");
    printf("      --audio-track N  one-based audio track for --check\n");
    printf("      --mdd FILE       companion MDD resources for MDX dictionaries\n");
    printf("      --font-file FILE embed this TrueType font in PDF output\n");
    printf("      --pdf-reflow     PDF -> DOCX/EPUB as editable text (default)\n");
    printf("      --pdf-pages      PDF -> DOCX/EPUB as page images instead of text\n");
    printf("      --pdfa [1b|2b|3b] write PDF/A (default 1b; requires --font-file)\n");
    printf("      --image-crop L,T,R,B  crop raster output by pixels\n");
    printf("      --image-resize WxH  resize raster output (0 keeps the aspect ratio)\n");
    printf("      --sheet N        one-based worksheet for CSV/TSV output\n");
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
#ifdef QUIREWISE_LINK_PIPELINE
    puts("  pipeline");
#endif
}

#if defined(QUIREWISE_LINK_PIPELINE)

typedef struct CliTarget {
    const char *name;
    QwOutputFormat format;
    const char *extension;
} CliTarget;

static const CliTarget cli_targets[] = {
    { "pdf", QW_FORMAT_PDF, "pdf" },
    { "txt", QW_FORMAT_TXT, "txt" },
    { "text", QW_FORMAT_TXT, "txt" },
    { "png", QW_FORMAT_PNG, "png" },
    /* Structured data writers (quirewise-data). */
    { "json", QW_FORMAT_JSON, "json" },
    { "jsonl", QW_FORMAT_JSONL, "jsonl" },
    { "yaml", QW_FORMAT_YAML, "yaml" },
    { "yml", QW_FORMAT_YAML, "yaml" },
    { "toml", QW_FORMAT_TOML, "toml" },
    { "xml", QW_FORMAT_XML, "xml" },
    { "vcf", QW_FORMAT_VCF, "vcf" },
    { "vcard", QW_FORMAT_VCF, "vcf" },
    /* Timed-cue writers (quirewise-subtitle). */
    { "srt", QW_FORMAT_SRT, "srt" },
    { "vtt", QW_FORMAT_VTT, "vtt" },
    { "lrc", QW_FORMAT_LRC, "lrc" },
    { "sub", QW_FORMAT_SUB, "sub" },
    { "ass", QW_FORMAT_ASS, "ass" },
    { "ssa", QW_FORMAT_SSA, "ssa" },
    { "sami", QW_FORMAT_SAMI, "sami" },
    { "scc", QW_FORMAT_SCC, "scc" },
    { "ttml", QW_FORMAT_TTML, "ttml" },
    { "opml", QW_FORMAT_OPML, "opml" },
    { "ipynb", QW_FORMAT_IPYNB, "ipynb" },
    /* Worksheet text writers (quirewise-spreadsheet). */
    { "csv", QW_FORMAT_CSV, "csv" },
    { "tsv", QW_FORMAT_TSV, "tsv" },
    { "xlsx", QW_FORMAT_XLSX, "xlsx" },
    { "ods", QW_FORMAT_ODS, "ods" },
    /* Layout text writers (quirewise/document + quirewise/text). */
    { "html", QW_FORMAT_HTML, "html" },
    { "md", QW_FORMAT_MARKDOWN, "md" },
    { "markdown", QW_FORMAT_MARKDOWN, "md" },
    /* Binary office writers (minimal DOCX/EPUB packages). */
    { "docx", QW_FORMAT_DOCX, "docx" },
    { "epub", QW_FORMAT_EPUB, "epub" },
    /* Raster re-encoding (quirewise-image writers). */
    { "bmp", QW_FORMAT_BMP, "bmp" },
    { "tiff", QW_FORMAT_TIFF, "tiff" },
    { "tif", QW_FORMAT_TIFF, "tif" },
    { "jpg", QW_FORMAT_JPG, "jpg" },
    { "jpeg", QW_FORMAT_JPG, "jpeg" },
    { "webp", QW_FORMAT_WEBP, "webp" },
    { "gif", QW_FORMAT_GIF, "gif" },
    { "hdr", QW_FORMAT_HDR, "hdr" },
    { "sgi", QW_FORMAT_SGI, "sgi" },
    { "pcx", QW_FORMAT_PCX, "pcx" },
    { "tga", QW_FORMAT_TGA, "tga" },
    { "qoi", QW_FORMAT_QOI, "qoi" },
    { "ppm", QW_FORMAT_PPM, "ppm" },
    { "htmlz", QW_FORMAT_HTMLZ, "htmlz" },
    { "txtz", QW_FORMAT_TXTZ, "txtz" },
    { "pmlz", QW_FORMAT_PMLZ, "pmlz" },
    { "hwpx", QW_FORMAT_HWPX, "hwpx" }
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

static int cli_has_extension(const char *path, const char *extension)
{
    const char *dot;
    size_t index = 0u;
    if (!path || !extension) return 0;
    dot = strrchr(path, '.');
    if (!dot || !dot[1] || !extension[0]) return 0;
    ++dot;
    while (dot[index] && extension[index]) {
        char a = dot[index];
        char b = extension[index];
        if (a >= 'A' && a <= 'Z') a = (char)(a - 'A' + 'a');
        if (b >= 'A' && b <= 'Z') b = (char)(b - 'A' + 'a');
        if (a != b) return 0;
        ++index;
    }
    return dot[index] == '\0' && extension[index] == '\0';
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

static int cli_run(const char *input, const char *output,
                   const char *target_name, int check, const char *out_dir,
                   int quiet, const QwAppOptions *app_options)
{
    const CliTarget *target = NULL;
    QwPipelineOptions pipeline_options;
    QwConvertReport report;
    char *default_output = NULL;
    const char *final_output = output;
    int status;

    pipeline_options.raster_page_mode = app_options->raster_page_mode;
    pipeline_options.pdz_page_rule = app_options->pdz_page_rule;
    pipeline_options.archive_password = app_options->archive_password;
    pipeline_options.pdf_password = app_options->pdf_password;
    pipeline_options.audio_track = app_options->audio_track;
    pipeline_options.mdd_path = app_options->mdd_path;
    pipeline_options.pdf_font_path = app_options->pdf_font_path;
    pipeline_options.pdf_office_reflow = app_options->pdf_office_reflow;
    pipeline_options.pdf_office_pages = app_options->pdf_office_pages;
    pipeline_options.pdfa_level = app_options->pdfa_level;
    pipeline_options.image_crop_left = app_options->image_crop_left;
    pipeline_options.image_crop_top = app_options->image_crop_top;
    pipeline_options.image_crop_right = app_options->image_crop_right;
    pipeline_options.image_crop_bottom = app_options->image_crop_bottom;
    pipeline_options.image_resize_width = app_options->image_resize_width;
    pipeline_options.image_resize_height = app_options->image_resize_height;
    pipeline_options.sheet_index = app_options->sheet_index;

    if (!check) {
        target = target_name ? cli_find_target(target_name)
                             : cli_find_target("pdf");
        if (!target) {
            fprintf(stderr, "error: unsupported target format '%s'\n",
                    target_name ? target_name : "");
            fprintf(stderr, "supported targets: pdf, txt, png, json, jsonl, yaml, toml, xml, vcf, srt, vtt, lrc, sub, ass, ssa, sami, scc, ttml, csv, tsv, xlsx, ods, html, md, docx, epub, bmp, tiff, jpg, webp, gif, hdr, sgi, pcx, tga, qoi, ppm, htmlz, txtz, pmlz, opml, ipynb,\n");
    printf("                       hwpx\n");
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
        if (!cli_has_extension(final_output, target->extension)) {
            fprintf(stderr,
                    "error: output name '%s' must end with .%s for --to %s\n",
                    final_output, target->extension, target->name);
            free(default_output);
            return 2;
        }
    } else if (target_name) {
        fprintf(stderr, "error: --to cannot be combined with --check\n");
        return 2;
    }

    memset(&report, 0, sizeof(report));
    if (check) {
        status = qw_pipeline_check_file(input, &pipeline_options, &report);
    } else {
        status = qw_pipeline_convert_file_to_format(input, final_output, target->format,
                                                    &pipeline_options, &report);
    }

    if (status == QW_STATUS_OK && !check && report.skipped_pages > 0u) {
        fprintf(stderr, "warning: %zu page(s) skipped", report.skipped_pages);
        if (report.note[0]) fprintf(stderr, ": %s", report.note);
        fprintf(stderr, "\n");
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

#endif /* QUIREWISE_LINK_PIPELINE */


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

static int cli_parse_u32(const char *text, unsigned *out)
{
    unsigned long value = 0u;
    size_t index = 0u;
    if (!text || !text[0]) return 0;
    for (; text[index]; ++index) {
        if (text[index] < '0' || text[index] > '9') return 0;
        value = value * 10ul + (unsigned long)(text[index] - '0');
        if (value > 100000ul) return 0;
    }
    *out = (unsigned)value;
    return 1;
}

static int cli_parse_crop(const char *text, unsigned values[4])
{
    size_t index;
    for (index = 0u; index < 4u; ++index) {
        const char *end = strchr(text, ',');
        char part[16];
        size_t length = end ? (size_t)(end - text) : strlen(text);
        if (!length || length >= sizeof(part)) return 0;
        memcpy(part, text, length);
        part[length] = '\0';
        if (!cli_parse_u32(part, &values[index])) return 0;
        if (!end) {
            return index == 3u;
        }
        text = end + 1;
    }
    return 1;
}

static int cli_parse_resize(const char *text, unsigned *width, unsigned *height)
{
    const char *separator = strchr(text, 'x');
    char part[16];
    size_t length;
    if (!separator) return 0;
    length = (size_t)(separator - text);
    if (!length || length >= sizeof(part)) return 0;
    memcpy(part, text, length);
    part[length] = '\0';
    if (!cli_parse_u32(part, width)) return 0;
    return cli_parse_u32(separator + 1, height);
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

static int quirewise_main(int argc, char **argv)
{
    const char *inputs[64];
    int input_count = 0;
    const char *output = NULL;
    const char *out_dir = NULL;
    const char *target_name = NULL;
    QwAppOptions app_options = { 1, 0, NULL, NULL, 0u, NULL, 0, 0, 0, 0, 0, 0, 0 };
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
        if (strcmp(argument, "--pdf-password") == 0) {
            if (index + 1 >= argc) {
                fprintf(stderr, "error: --pdf-password requires text\n");
                return 2;
            }
            app_options.pdf_password = argv[++index];
            continue;
        }
        if (strcmp(argument, "--sheet") == 0) {
            unsigned sheet = 0u;
            if (index + 1 >= argc || !cli_parse_u32(argv[index + 1], &sheet) ||
                sheet == 0u) {
                fprintf(stderr, "error: --sheet expects a one-based sheet number\n");
                return 2;
            }
            app_options.sheet_index = sheet - 1u;
            ++index;
            continue;
        }
        if (strcmp(argument, "--image-crop") == 0) {
            unsigned values[4];
            if (index + 1 >= argc ||
                !cli_parse_crop(argv[index + 1], values)) {
                fprintf(stderr, "error: --image-crop expects L,T,R,B\n");
                return 2;
            }
            app_options.image_crop_left = values[0];
            app_options.image_crop_top = values[1];
            app_options.image_crop_right = values[2];
            app_options.image_crop_bottom = values[3];
            ++index;
            continue;
        }
        if (strcmp(argument, "--image-resize") == 0) {
            if (index + 1 >= argc ||
                !cli_parse_resize(argv[index + 1],
                                  &app_options.image_resize_width,
                                  &app_options.image_resize_height)) {
                fprintf(stderr, "error: --image-resize expects WxH\n");
                return 2;
            }
            ++index;
            continue;
        }
        if (strcmp(argument, "--mdd") == 0) {
            if (index + 1 >= argc) {
                fprintf(stderr, "error: --mdd requires a file path\n");
                return 2;
            }
            app_options.mdd_path = argv[++index];
            continue;
        }
        if (strcmp(argument, "--pdf-reflow") == 0) {
            app_options.pdf_office_reflow = 1;
            continue;
        }
        if (strcmp(argument, "--pdf-pages") == 0) {
            app_options.pdf_office_pages = 1;
            continue;
        }
        if (strcmp(argument, "--pdfa") == 0) {
            app_options.pdfa_level = QW_PDFA_1B;
            if (index + 1 < argc && strcmp(argv[index + 1], "1b") == 0) {
                app_options.pdfa_level = QW_PDFA_1B;
                ++index;
            } else if (index + 1 < argc && strcmp(argv[index + 1], "2b") == 0) {
                app_options.pdfa_level = QW_PDFA_2B;
                ++index;
            } else if (index + 1 < argc && strcmp(argv[index + 1], "3b") == 0) {
                app_options.pdfa_level = QW_PDFA_3B;
                ++index;
            } else if (index + 1 < argc && strcmp(argv[index + 1], "1a") == 0) {
                fprintf(stderr, "error: PDF/A-1a is not supported; use 1b, 2b or 3b\n");
                return 2;
            }
            continue;
        }
        if (strcmp(argument, "--font-file") == 0) {
            if (index + 1 >= argc) {
                fprintf(stderr, "error: --font-file requires a file path\n");
                return 2;
            }
            app_options.pdf_font_path = argv[++index];
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
    if (check && out_dir) {
        fprintf(stderr, "error: --out-dir cannot be combined with --check\n");
        return 2;
    }

#if defined(QUIREWISE_LINK_PIPELINE)
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
            "error: this build does not link quirewise-pipeline; "
            "conversions are unavailable\n");
    return 2;
#endif
}

/*
 * Windows entry point.
 *
 * The C runtime hands MinGW/MSVC `main` arguments in the active ANSI code
 * page, while every Quirewise API takes UTF-8 paths. Reading the wide command
 * line and converting to UTF-8 keeps non-ASCII input and output names working
 * on every console code page.
 */
#if defined(_WIN32)

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include <shellapi.h>

static char *qw_utf8_from_wide(const wchar_t *text)
{
    int length;
    char *utf8;

    if (!text) return NULL;
    length = WideCharToMultiByte(CP_UTF8, 0, text, -1, NULL, 0, NULL, NULL);
    if (length <= 0) return NULL;
    utf8 = (char *)malloc((size_t)length);
    if (!utf8) return NULL;
    if (WideCharToMultiByte(CP_UTF8, 0, text, -1, utf8, length, NULL, NULL) <=
        0) {
        free(utf8);
        return NULL;
    }
    return utf8;
}

int main(void)
{
    int argc = 0;
    int index;
    int rc = 2;
    wchar_t **wide_argv = CommandLineToArgvW(GetCommandLineW(), &argc);
    char **argv;

    if (!wide_argv || argc <= 0) {
        if (wide_argv) LocalFree(wide_argv);
        return 2;
    }
    argv = (char **)calloc((size_t)argc + 1u, sizeof(char *));
    if (!argv) {
        LocalFree(wide_argv);
        return 2;
    }
    for (index = 0; index < argc; ++index) {
        argv[index] = qw_utf8_from_wide(wide_argv[index]);
        if (!argv[index]) goto done;
    }
    rc = quirewise_main(argc, argv);

done:
    for (index = 0; index < argc; ++index) free(argv[index]);
    free(argv);
    LocalFree(wide_argv);
    return rc;
}

#else

int main(int argc, char **argv)
{
    return quirewise_main(argc, argv);
}

#endif
