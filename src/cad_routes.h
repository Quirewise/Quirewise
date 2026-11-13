#ifndef QUIREWISE_APP_CAD_ROUTES_H
#define QUIREWISE_APP_CAD_ROUTES_H

#include "app_options.h"

#include <quirewise/convert.h>
#include <quirewise/status.h>

#include <stddef.h>
#include <stdint.h>

/* Convert a DXF drawing to a one-page PDF. The raster page is produced by the
 * vector package's CAD renderer; text is currently drawn as placeholder bars
 * (the text inventory is still available through the library API). */
int qw_app_cad_convert_file(const char *input_path,
                            const QwAppOptions *options,
                            uint8_t **out_pdf, size_t *out_size,
                            QwConvertReport *report);

/* Parse-only check for a CAD file. */
int qw_app_cad_check_file(const char *input_path, QwConvertReport *report);

/* Extract the drawing text inventory as UTF-8, one entity per line. */
int qw_app_cad_extract_text(const char *input_path, uint8_t **out_text,
                            size_t *out_size, QwConvertReport *report);

#endif
