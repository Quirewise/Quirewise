#include "data_routes.h"

#include <quirewise/data.h>
#include <quirewise/status.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define QW_DATA_ROUTE_MAX_INPUT (256u * 1024u * 1024u)
#define QW_DATA_ROUTE_MAX_DEPTH 64u
#define QW_DATA_ROUTE_MAX_NODES 200000u

typedef struct DataHtml {
    char *data;
    size_t size;
    size_t capacity;
} DataHtml;

static int data_iequals(const char *left, const char *right)
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

static int data_extension_format(const char *path, QwDataFormat *out)
{
    const char *dot = strrchr(path, '.');
    if (!dot) return 0;
    ++dot;
    if (data_iequals(dot, "json")) *out = QW_DATA_FORMAT_JSON;
    else if (data_iequals(dot, "jsonl") || data_iequals(dot, "ndjson"))
        *out = QW_DATA_FORMAT_JSONL;
    else if (data_iequals(dot, "yaml") || data_iequals(dot, "yml"))
        *out = QW_DATA_FORMAT_YAML;
    else if (data_iequals(dot, "toml")) *out = QW_DATA_FORMAT_TOML;
    else if (data_iequals(dot, "xml")) *out = QW_DATA_FORMAT_XML;
    else if (data_iequals(dot, "opml")) *out = QW_DATA_FORMAT_OPML;
    else if (data_iequals(dot, "ipynb")) *out = QW_DATA_FORMAT_IPYNB;
    else if (data_iequals(dot, "vcf") || data_iequals(dot, "vcard"))
        *out = QW_DATA_FORMAT_VCARD;
    else return 0;
    return 1;
}

static int html_reserve(DataHtml *html, size_t extra)
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

static int html_append(DataHtml *html, const char *text, size_t length)
{
    if (!html_reserve(html, length)) return 0;
    if (length) memcpy(html->data + html->size, text, length);
    html->size += length;
    html->data[html->size] = '\0';
    return 1;
}

static int html_escape(DataHtml *html, const char *text, size_t length)
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

static int render_value(DataHtml *html, const QwDataValue *value,
                        unsigned depth, size_t *budget);

static int render_scalar(DataHtml *html, const QwDataValue *value)
{
    QwDataKind kind = qw_data_value_kind(value);
    if (kind == QW_DATA_KIND_NULL) return html_append(html, "null", 4u);
    if (kind == QW_DATA_KIND_BOOLEAN) {
        int flag = 0;
        if (qw_data_value_boolean(value, &flag) != QW_DATA_OK) return 0;
        return html_append(html, flag ? "true" : "false", flag ? 4u : 5u);
    }
    {
        const char *text = NULL;
        size_t size = 0u;
        if (qw_data_value_text(value, &text, &size) != QW_DATA_OK || !text)
            return 0;
        return html_escape(html, text, size);
    }
}

static int render_value(DataHtml *html, const QwDataValue *value,
                        unsigned depth, size_t *budget)
{
    QwDataKind kind;
    size_t count;
    size_t index;

    if (!value) return html_append(html, "null", 4u);
    if (depth > QW_DATA_ROUTE_MAX_DEPTH) return 0;
    if (*budget == 0u) return 0;
    --*budget;
    kind = qw_data_value_kind(value);
    if (kind == QW_DATA_KIND_OBJECT) {
        if (!html_append(html, "<table>", 7u)) return 0;
        count = qw_data_value_count(value);
        for (index = 0u; index < count; ++index) {
            const QwDataValue *child;
            const char *key = NULL;
            size_t key_size = 0u;
            child = qw_data_object_at(value, index, &key, &key_size);
            if (!html_append(html, "<tr><td>", 8u) ||
                (key && key_size &&
                 !html_escape(html, key, key_size)) ||
                !html_append(html, "</td><td>", 9u) ||
                !render_value(html, child, depth + 1u, budget) ||
                !html_append(html, "</td></tr>", 10u))
                return 0;
            if (*budget == 0u) return 0;
        }
        return html_append(html, "</table>", 8u);
    }
    if (kind == QW_DATA_KIND_ARRAY) {
        if (!html_append(html, "<ul>", 4u)) return 0;
        count = qw_data_value_count(value);
        for (index = 0u; index < count; ++index) {
            if (!html_append(html, "<li>", 4u) ||
                !render_value(html, qw_data_array_at(value, index),
                              depth + 1u, budget) ||
                !html_append(html, "</li>", 5u))
                return 0;
        }
        return html_append(html, "</ul>", 5u);
    }
    return render_scalar(html, value);
}

static const char *data_format_label(QwDataFormat format)
{
    switch (format) {
    case QW_DATA_FORMAT_JSON: return "JSON";
    case QW_DATA_FORMAT_JSONL: return "JSONL";
    case QW_DATA_FORMAT_YAML: return "YAML";
    case QW_DATA_FORMAT_TOML: return "TOML";
    case QW_DATA_FORMAT_XML: return "XML";
    case QW_DATA_FORMAT_OPML: return "OPML";
    case QW_DATA_FORMAT_IPYNB: return "IPYNB";
    case QW_DATA_FORMAT_VCARD: return "vCard";
    default: return "data";
    }
}

int qw_app_data_convert_file(const char *path,
                             uint8_t **out_pdf, size_t *out_size,
                             QwConvertReport *report)
{
    QwDataFormat format;
    QwDataDocument *document = NULL;
    QwDataStatus status;
    DataHtml html;
    FILE *file;
    long length;
    uint8_t *data;
    size_t budget = QW_DATA_ROUTE_MAX_NODES;
    int rc = QW_STATUS_OK;

    if (!path || !out_pdf || !out_size) return QW_STATUS_ERR_INVALID_ARGUMENT;
    *out_pdf = NULL;
    *out_size = 0u;
    if (!data_extension_format(path, &format))
        return QW_STATUS_ERR_UNSUPPORTED;
    file = fopen(path, "rb");
    if (!file) return QW_STATUS_ERR_IO;
    if (fseek(file, 0, SEEK_END) != 0 || (length = ftell(file)) < 0 ||
        fseek(file, 0, SEEK_SET) != 0) {
        fclose(file);
        return QW_STATUS_ERR_IO;
    }
    if ((unsigned long)length > (unsigned long)QW_DATA_ROUTE_MAX_INPUT) {
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

    status = qw_data_parse(format, data, (size_t)length, &document);
    free(data);
    if (status != QW_DATA_OK || !document) {
        if (report) snprintf(report->note, sizeof(report->note),
                             "structured-data parse failed with status %d",
                             (int)status);
        return QW_STATUS_ERR_FORMAT;
    }
    memset(&html, 0, sizeof(html));
    if (!html_append(&html, "<html><body><h1>",
                     strlen("<html><body><h1>")) ||
        !html_append(&html, data_format_label(format),
                     strlen(data_format_label(format))) ||
        !html_append(&html, "</h1><table><tr><td>",
                     strlen("</h1><table><tr><td>")))
        goto oom;
    if (!render_value(&html, qw_data_document_root(document), 0u, &budget))
        goto oom;
    if (!html_append(&html, "</td></tr></table></body></html>",
                     strlen("</td></tr></table></body></html>")))
        goto oom;

    rc = qw_convert_to_pdf_memory(html.data, html.size, NULL, out_pdf,
                                  out_size, report);
    if (rc == QW_STATUS_OK && report) {
        snprintf(report->note, sizeof(report->note),
                 "%s value tree rendered as tables/lists",
                 data_format_label(format));
        report->output_size = *out_size;
    }
    free(html.data);
    qw_data_document_free(document);
    return rc;

oom:
    free(html.data);
    qw_data_document_free(document);
    return QW_STATUS_ERR_OUT_OF_MEMORY;
}
