#ifndef QUIREWISE_APP_FILE_H
#define QUIREWISE_APP_FILE_H

/*
 * UTF-8 path helper shared by the application routes.
 *
 * The library entry points accept UTF-8 paths and open them with _wfopen on
 * Windows. The route modules used plain fopen(), so a CJK or emoji file name
 * failed when a route opened it directly. Route code must use this helper
 * instead of fopen().
 */

#include <stdio.h>

#if defined(_WIN32)

#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>

#include <stdlib.h>

static FILE *qw_app_fopen_utf8(const char *path, const char *mode)
{
    wchar_t wide_mode[16];
    wchar_t *wide_path = NULL;
    int length;
    size_t index = 0u;
    FILE *file = NULL;

    if (!path || !mode) return NULL;
    while (mode[index] && index + 1u < sizeof(wide_mode) / sizeof(wide_mode[0])) {
        wide_mode[index] = (wchar_t)(unsigned char)mode[index];
        ++index;
    }
    wide_mode[index] = L'\0';

    length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, NULL,
                                 0);
    if (length <= 0) return NULL;
    wide_path = (wchar_t *)malloc((size_t)length * sizeof(wchar_t));
    if (!wide_path) return NULL;
    if (MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, wide_path,
                            length) <= 0) {
        free(wide_path);
        return NULL;
    }
    file = _wfopen(wide_path, wide_mode);
    free(wide_path);
    return file;
}

#else

static FILE *qw_app_fopen_utf8(const char *path, const char *mode)
{
    return fopen(path, mode);
}

#endif

#endif
