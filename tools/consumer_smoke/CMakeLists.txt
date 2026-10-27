cmake_minimum_required(VERSION 3.21)
project(QuirewiseConsumerSmoke LANGUAGES C)

find_package(QuirewiseImage CONFIG REQUIRED)
find_package(QuirewiseArchive CONFIG REQUIRED)
find_package(QuirewiseData CONFIG REQUIRED)
find_package(QuirewiseText CONFIG REQUIRED)
find_package(QuirewisePage CONFIG REQUIRED)
find_package(QuirewiseDocument CONFIG REQUIRED)
find_package(QuirewiseEbook CONFIG REQUIRED)
find_package(QuirewiseSpreadsheet CONFIG REQUIRED)
find_package(QuirewiseAudio CONFIG REQUIRED)
find_package(QuirewiseSubtitle CONFIG REQUIRED)
find_package(QuirewiseVector CONFIG REQUIRED)
find_package(QuirewiseComic CONFIG REQUIRED)
find_package(QuirewisePDG CONFIG REQUIRED)
find_package(QuirewiseRuntime CONFIG REQUIRED)

add_executable(quirewise_consumer_smoke main.c)
target_compile_features(quirewise_consumer_smoke PRIVATE c_std_11)
target_link_libraries(quirewise_consumer_smoke PRIVATE
    Quirewise::Runtime
    Quirewise::Image
    Quirewise::Archive
    Quirewise::Data
    Quirewise::Text
    Quirewise::Page
    Quirewise::Document
    Quirewise::Ebook
    Quirewise::Spreadsheet
    Quirewise::Audio
    Quirewise::Subtitle
    Quirewise::Vector
    Quirewise::Comic
    Quirewise::PDG)
