cmake_minimum_required(VERSION 3.21)
project(Quirewise VERSION 0.2.2 LANGUAGES C)

include(GNUInstallDirs)

option(QUIREWISE_VALIDATE_DEPENDENCIES
    "Add a target that validates the workspace dependency graph" OFF)

option(QUIREWISE_BUILD_PDF_VERIFIER
    "Build the render-based PDF verification tool" OFF)

option(QUIREWISE_LINK_RUNTIME "Link the independent Quirewise runtime library" OFF)
option(QUIREWISE_LINK_IMAGE "Link quirewise-image" OFF)
option(QUIREWISE_LINK_ARCHIVE "Link quirewise-archive" OFF)
option(QUIREWISE_LINK_PAGE "Link quirewise-page" OFF)
option(QUIREWISE_LINK_PDG "Link quirewise-pdg" OFF)
option(QUIREWISE_LINK_DOCUMENT "Link quirewise-document" OFF)
option(QUIREWISE_LINK_EBOOK "Link quirewise-ebook" OFF)
option(QUIREWISE_LINK_TEXT "Link quirewise-text" OFF)
option(QUIREWISE_LINK_DATA "Link quirewise-data" OFF)
option(QUIREWISE_LINK_SPREADSHEET "Link quirewise-spreadsheet" OFF)
option(QUIREWISE_LINK_AUDIO "Link quirewise-audio" OFF)
option(QUIREWISE_LINK_SUBTITLE "Link quirewise-subtitle" OFF)
option(QUIREWISE_LINK_VECTOR "Link quirewise-vector" OFF)
option(QUIREWISE_LINK_COMIC "Link quirewise-comic" OFF)

add_executable(quirewise src/main.c)
target_compile_features(quirewise PRIVATE c_std_11)
target_compile_definitions(quirewise PRIVATE
    QUIREWISE_APP_VERSION="${PROJECT_VERSION}")
if(WIN32)
    # CommandLineToArgvW is used by the Windows entry point to receive UTF-8
    # command line arguments.
    target_link_libraries(quirewise PRIVATE shell32)
endif()

set(QW_LINK_TARGETS)
macro(quirewise_find_library option_name package_name target_name define_name)
    if(${option_name})
        find_package(${package_name} CONFIG REQUIRED)
        target_compile_definitions(quirewise PRIVATE ${define_name})
        list(APPEND QW_LINK_TARGETS ${target_name})
    endif()
endmacro()

quirewise_find_library(QUIREWISE_LINK_RUNTIME QuirewiseRuntime Quirewise::Runtime QUIREWISE_LINK_RUNTIME)
quirewise_find_library(QUIREWISE_LINK_IMAGE QuirewiseImage Quirewise::Image QUIREWISE_LINK_IMAGE)
quirewise_find_library(QUIREWISE_LINK_ARCHIVE QuirewiseArchive Quirewise::Archive QUIREWISE_LINK_ARCHIVE)
quirewise_find_library(QUIREWISE_LINK_PAGE QuirewisePage Quirewise::Page QUIREWISE_LINK_PAGE)
quirewise_find_library(QUIREWISE_LINK_PDG QuirewisePDG Quirewise::PDG QUIREWISE_LINK_PDG)
quirewise_find_library(QUIREWISE_LINK_DOCUMENT QuirewiseDocument Quirewise::Document QUIREWISE_LINK_DOCUMENT)
quirewise_find_library(QUIREWISE_LINK_EBOOK QuirewiseEbook Quirewise::Ebook QUIREWISE_LINK_EBOOK)
quirewise_find_library(QUIREWISE_LINK_TEXT QuirewiseText Quirewise::Text QUIREWISE_LINK_TEXT)
quirewise_find_library(QUIREWISE_LINK_DATA QuirewiseData Quirewise::Data QUIREWISE_LINK_DATA)
quirewise_find_library(QUIREWISE_LINK_SPREADSHEET QuirewiseSpreadsheet Quirewise::Spreadsheet QUIREWISE_LINK_SPREADSHEET)
quirewise_find_library(QUIREWISE_LINK_AUDIO QuirewiseAudio Quirewise::Audio QUIREWISE_LINK_AUDIO)
quirewise_find_library(QUIREWISE_LINK_SUBTITLE QuirewiseSubtitle Quirewise::Subtitle QUIREWISE_LINK_SUBTITLE)
quirewise_find_library(QUIREWISE_LINK_VECTOR QuirewiseVector Quirewise::Vector QUIREWISE_LINK_VECTOR)
quirewise_find_library(QUIREWISE_LINK_COMIC QuirewiseComic Quirewise::Comic QUIREWISE_LINK_COMIC)

target_link_libraries(quirewise PRIVATE ${QW_LINK_TARGETS})

if(QUIREWISE_LINK_DOCUMENT AND QUIREWISE_LINK_PAGE AND QUIREWISE_LINK_PDG AND QUIREWISE_LINK_IMAGE)
    target_sources(quirewise PRIVATE src/page_routes.c)
    target_compile_definitions(quirewise PRIVATE QUIREWISE_APP_PAGE_ROUTES)
endif()

if(QUIREWISE_LINK_DOCUMENT AND QUIREWISE_LINK_SUBTITLE)
    target_sources(quirewise PRIVATE src/subtitle_routes.c)
    target_compile_definitions(quirewise PRIVATE QUIREWISE_APP_SUBTITLE_ROUTES)
endif()

if(QUIREWISE_LINK_DOCUMENT AND QUIREWISE_LINK_AUDIO)
    target_sources(quirewise PRIVATE src/audio_check.c)
    target_compile_definitions(quirewise PRIVATE QUIREWISE_APP_AUDIO_CHECK)
endif()

if(QUIREWISE_LINK_DOCUMENT AND QUIREWISE_LINK_DATA)
    target_sources(quirewise PRIVATE src/data_routes.c)
    target_compile_definitions(quirewise PRIVATE QUIREWISE_APP_DATA_ROUTES)
endif()

if(QUIREWISE_LINK_DOCUMENT AND QUIREWISE_LINK_COMIC AND QUIREWISE_LINK_IMAGE)
    target_sources(quirewise PRIVATE src/comic_routes.c)
    target_compile_definitions(quirewise PRIVATE QUIREWISE_APP_COMIC_ROUTES)
endif()

if(QUIREWISE_LINK_DOCUMENT AND QUIREWISE_LINK_VECTOR)
    target_sources(quirewise PRIVATE src/cad_routes.c)
    target_compile_definitions(quirewise PRIVATE QUIREWISE_APP_CAD_ROUTES)
endif()

if(QUIREWISE_LINK_DOCUMENT AND QUIREWISE_LINK_VECTOR)
    target_sources(quirewise PRIVATE src/svg_routes.c)
    target_compile_definitions(quirewise PRIVATE QUIREWISE_APP_SVG_ROUTES)
endif()

if(QUIREWISE_VALIDATE_DEPENDENCIES)
    find_package(Python3 COMPONENTS Interpreter REQUIRED)
    add_custom_target(quirewise_validate_dependencies
        COMMAND "${Python3_EXECUTABLE}"
                "${CMAKE_CURRENT_SOURCE_DIR}/tools/validate_dependency_graph.py"
                --workspace "${CMAKE_CURRENT_SOURCE_DIR}/.."
        WORKING_DIRECTORY "${CMAKE_CURRENT_SOURCE_DIR}"
        VERBATIM)
endif()

if(QUIREWISE_BUILD_PDF_VERIFIER)
    if(NOT QUIREWISE_LINK_DOCUMENT)
        message(FATAL_ERROR
            "QUIREWISE_BUILD_PDF_VERIFIER requires QUIREWISE_LINK_DOCUMENT=ON")
    endif()
    add_executable(quirewise_verify_pdf_pages tools/verify_pdf_pages.c)
    target_compile_features(quirewise_verify_pdf_pages PRIVATE c_std_11)
    target_link_libraries(quirewise_verify_pdf_pages PRIVATE ${QW_LINK_TARGETS})
    if(WIN32)
        target_link_libraries(quirewise_verify_pdf_pages PRIVATE shell32)
    endif()
    install(TARGETS quirewise_verify_pdf_pages
        RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
endif()

install(TARGETS quirewise RUNTIME DESTINATION "${CMAKE_INSTALL_BINDIR}")
