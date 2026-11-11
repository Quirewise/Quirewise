#ifndef QUIREWISE_APP_DATA_ROUTES_H
#define QUIREWISE_APP_DATA_ROUTES_H

#include <quirewise/convert.h>

#include <stddef.h>
#include <stdint.h>

/* Convert JSON/JSONL/YAML/TOML/XML/OPML/IPYNB/vCard to PDF through a
 * typed value tree rendered as HTML. Returns QW_STATUS_ERR_UNSUPPORTED when
 * the extension is not a supported structured-data format. */
int qw_app_data_convert_file(const char *path,
                             uint8_t **out_pdf, size_t *out_size,
                             QwConvertReport *report);

#endif
