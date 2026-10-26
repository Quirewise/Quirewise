#include <stdio.h>
#include <string.h>

static void print_help(const char *name)
{
    printf("Quirewise application shell\n\n");
    printf("Usage: %s [--version|--libraries|--help]\n", name);
    printf("The application consumes independent Quirewise libraries installed as CMake packages.\n");
}

int main(int argc, char **argv)
{
    if (argc <= 1 || strcmp(argv[1], "--help") == 0) {
        print_help(argv[0]);
        return 0;
    }
    if (strcmp(argv[1], "--version") == 0) {
        puts("Quirewise application 0.1.0");
        return 0;
    }
    if (strcmp(argv[1], "--libraries") == 0) {
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
#ifdef QUIREWISE_LINK_PAGE
        puts("  page");
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
        return 0;
    }
    fprintf(stderr, "Unknown option: %s\n", argv[1]);
    return 2;
}
