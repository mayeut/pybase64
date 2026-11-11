cmake_minimum_required(VERSION 3.15...4.4)
project(${SKBUILD_PROJECT_NAME} LANGUAGES C)

if(CMAKE_CROSSCOMPILING)
  find_package(Python COMPONENTS Development.Module REQUIRED)
else()
  find_package(Python COMPONENTS Interpreter Development.Module REQUIRED)
endif()

set(CMAKE_POSITION_INDEPENDENT_CODE ON)

set(BUILD_SHARED_LIBS OFF CACHE INTERNAL "" FORCE)

set(BASE64_BUILD_CLI OFF CACHE INTERNAL "" FORCE)
set(BASE64_BUILD_TESTS OFF CACHE INTERNAL "" FORCE)
set(BASE64_WITH_OpenMP OFF CACHE INTERNAL "" FORCE)
set(BASE64_REGENERATE_TABLES OFF CACHE INTERNAL "" FORCE)

add_subdirectory(base64 EXCLUDE_FROM_ALL)

python_add_library(_pybase64 MODULE src/${SKBUILD_PROJECT_NAME}/_pybase64.c src/${SKBUILD_PROJECT_NAME}/_pybase64_get_simd_flags.c WITH_SOABI)
target_link_libraries(_pybase64 PRIVATE base64)
target_include_directories(_pybase64 PRIVATE "${CMAKE_CURRENT_BINARY_DIR}/base64" "${CMAKE_CURRENT_SOURCE_DIR}/base64/lib")

install(TARGETS _pybase64 DESTINATION ${SKBUILD_PROJECT_NAME})
