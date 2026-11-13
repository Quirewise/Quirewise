#include "subtitle_routes.h"

#include "app_file.h"

#include <quirewise/status.h>
#include <quirewise/subtitle.h>

#include <stdarg.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define QW_SUBTITLE_ROUTE_MAX_INPUT (256u * 1024u * 1024u)

typedef struct SubtitleHtml {
    char *data;
    size_t size;
    size_t capacity;
} SubtitleHtml;

static int subtitle_iequals(const char *left, const char *right)
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

static int subtitle_extension_format(const char *path,
                                     QwSubtitleInputFormat *out)
{
    const char *dot = strrchr(path, '.');
    if (!dot) return 0;
    ++dot;
    if (subtitle_iequals(dot, "srt")) *out = QW_SUBTITLE_INPUT_SRT;
    else if (subtitle_iequals(dot, "vtt")) *out = QW_SUBTITLE_INPUT_VTT;
    else if (subtitle_iequals(dot, "lrc")) *out = QW_SUBTITLE_INPUT_LRC;
    else if (subtitle_iequals(dot, "ass")) *out = QW_SUBTITLE_INPUT_ASS;
    else if (subtitle_iequals(dot, "ssa")) *out = QW_SUBTITLE_INPUT_SSA;
    else if (subtitle_iequals(dot, "smi") || subtitle_iequals(dot, "sami"))
        *out = QW_SUBTITLE_INPUT_SAMI;
    else if (subtitle_iequals(dot, "sub")) *out = QW_SUBTITLE_INPUT_MICRODVD;
    else if (subtitle_iequals(dot, "scc")) *out = QW_SUBTITLE_INPUT_SCC;
    else return 0;
    return 1;
}

static int html_reserve(SubtitleHtml *html, size_t extra)
{
    size_t needed = html->size + extra;
    size_t capacity;
    char *grown;
    if (needed < html->size) return 0;
    if (needed + 1u <= html->capacity) return 1;
    capacity = html->capacity ? html->capacity : 4096u;
    while (capacity < needed + 1u) {
        if (capacity > (size_t)-1 / 2u) return 0;
        capacity *= 2u;
    }
    grown = (char *)realloc(html->data, capacity);
    if (!grown) return 0;
    html->data = grown;
    html->capacity = capacity;
    return 1;
}

static int html_append(SubtitleHtml *html, const char *text, size_t length)
{
    if (!html_reserve(html, length)) return 0;
    if (length) memcpy(html->data + html->size, text, length);
    html->size += length;
    html->data[html->size] = '\0';
    return 1;
}

static int html_printf(SubtitleHtml *html, const char *format, ...)
{
    char text[256];
    va_list args;
    int length;
    va_start(args, format);
    length = vsnprintf(text, sizeof(text), format, args);
    va_end(args);
    if (length < 0 || (size_t)length >= sizeof(text)) return 0;
    return html_append(html, text, (size_t)length);
}

static int html_escape(SubtitleHtml *html, const char *text, size_t length)
{
    size_t index;
    for (index = 0u; index < length; ++index) {
        const char *replacement = NULL;
        switch (text[index]) {
        case '&': replacement = "&amp;"; break;
        case '<': replacement = "&lt;"; break;
        case '>': replacement = "&gt;"; break;
        case '"': replacement = "&quot;"; break;
        case '\n': replacement = "<br/>"; break;
        case '\r': continue;
        default: break;
        }
        if (replacement) {
            if (!html_append(html, replacement, strlen(replacement))) return 0;
        } else if (!html_append(html, text + index, 1u)) {
            return 0;
        }
    }
    return 1;
}

static void format_time(char *out, size_t capacity, uint64_t milliseconds)
{
    uint64_t total_seconds = milliseconds / 1000u;
    snprintf(out, capacity, "%02llu:%02llu:%02llu.%03llu",
             (unsigned long long)(total_seconds / 3600u),
             (unsigned long long)((total_seconds / 60u) % 60u),
             (unsigned long long)(total_seconds % 60u),
             (unsigned long long)(milliseconds % 1000u));
}

int qw_app_subtitle_convert_file(const char *path,
                                 uint8_t **out_pdf, size_t *out_size,
                                 QwConvertReport *report)
{
    QwSubtitleInputFormat format;
    QwSubtitle *document = NULL;
    QwSubtitleInfo info;
    QwSubtitleStatus status;
    SubtitleHtml html;
    FILE *file;
    long length;
    uint8_t *data;
    size_t index;
    int rc = QW_STATUS_OK;

    if (!path || !out_pdf || !out_size) return QW_STATUS_ERR_INVALID_ARGUMENT;
    *out_pdf = NULL;
    *out_size = 0u;
    if (!subtitle_extension_format(path, &format))
        return QW_STATUS_ERR_UNSUPPORTED;
    file = qw_app_fopen_utf8(path, "rb");
    if (!file) return QW_STATUS_ERR_IO;
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    if ((unsigned long)length > (unsigned long)QW_SUBTITLE_ROUTE_MAX_INPUT) {
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

    status = qw_subtitle_parse(data, (size_t)length, format, &document);
    free(data);
    if (status != QW_SUBTITLE_OK || !document) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "subtitle parse failed with status %d",
                             (int)status);
        return QW_STATUS_ERR_FORMAT;
    }
    memset(&info, 0, sizeof(info));
    qw_subtitle_get_info(document, &info);

    memset(&html, 0, sizeof(html));
    if (!html_append(&html, "<html><body><h1>Subtitles</h1>",
                     strlen("<html><body><h1>Subtitles</h1>")))
        goto oom;
    for (index = 0u; index < info.cue_count; ++index) {
        QwSubtitleCueView cue;
        char start_time[32];
        char end_time[32];
        memset(&cue, 0, sizeof(cue));
        if (qw_subtitle_get_cue(document, index, &cue) != QW_SUBTITLE_OK)
            continue;
        format_time(start_time, sizeof(start_time), cue.start_milliseconds);
        format_time(end_time, sizeof(end_time), cue.end_milliseconds);
        if (!html_printf(&html, "<p><b>%s -&gt; %s</b><br/>", start_time,
                         end_time) ||
            (cue.text && cue.text_size &&
             !html_escape(&html, cue.text, cue.text_size)) ||
            !html_append(&html, "</p>", 4u))
            goto oom;
    }
    if (!html_append(&html, "</body></html>", strlen("</body></html>")))
        goto oom;

    rc = qw_convert_to_pdf_memory(html.data, html.size, NULL, out_pdf,
                                  out_size, report);
    if (rc == QW_STATUS_OK && report) {
        snprintf(report->note, sizeof(report->note),
                 "subtitle layout: %zu cue(s) rendered as text pages",
                 info.cue_count);
        report->output_size = *out_size;
    }
    free(html.data);
    qw_subtitle_free(document);
    return rc;

oom:
    free(html.data);
    qw_subtitle_free(document);
    return QW_STATUS_ERR_OUT_OF_MEMORY;
}
