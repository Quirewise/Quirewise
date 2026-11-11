#ifndef QUIREWISE_APP_OPTIONS_H
#define QUIREWISE_APP_OPTIONS_H

#include <stddef.h>

typedef struct QwAppOptions {
    /* QW_RASTER_PAGE_MODE_A4 or QW_RASTER_PAGE_MODE_IMAGE. */
    int raster_page_mode;
    /* PDZ_PDF_PAGES_AUTO/BODY/BODY_ATT/ALL for PDG containers. */
    int pdz_page_rule;
    const char *archive_password;
    size_t audio_track;
} QwAppOptions;

#endif
