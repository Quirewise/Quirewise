#ifndef QUIREWISE_APP_SVG_ROUTES_H
#define QUIREWISE_APP_SVG_ROUTES_H

#include <quirewise/format.h>
#include <quirewise/status.h>

#include <stddef.h>
#include <stdint.h>

#include "app_options.h"

/* Convert an SVG/SVGZ file to a single-page raster PDF. */
int qw_app_svg_convert_file(const char *path, const QwAppOptions *options,
                            uint8_t **out_pdf, size_t *out_size,
                            QwConvertReport *report);

/* Validate SVG/SVGZ by rendering it and discarding the PDF. */
int qw_app_svg_check_file(const char *path, QwConvertReport *report);

#endif
