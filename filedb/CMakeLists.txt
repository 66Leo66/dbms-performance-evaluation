
cmake_minimum_required(VERSION 3.20)
project(MyProject LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

add_executable(FileDB main.cpp)

# Release: aggressive optimization
# Debug: sanitizers
if (MSVC)
    target_compile_options(FileDB PRIVATE
            $<$<CONFIG:Release>:/O2>
            $<$<CONFIG:Debug>:/fsanitize=address>
    )
elseif (CMAKE_CXX_COMPILER_ID MATCHES "GNU|Clang|AppleClang")
    target_compile_options(FileDB PRIVATE
            $<$<CONFIG:Release>:-O3>
            $<$<CONFIG:Release>:-march=native>

            $<$<CONFIG:Debug>:-g>
            $<$<CONFIG:Debug>:-fno-omit-frame-pointer>
            "$<$<CONFIG:Debug>:-fsanitize=address,undefined>"
            "$<$<CONFIG:Debug>:-fno-sanitize-recover=all>"
    )

    target_link_options(FileDB PRIVATE
            "$<$<CONFIG:Debug>:-fsanitize=address,undefined>"
    )
endif ()

# LTO: Release only
include(CheckIPOSupported)
check_ipo_supported(RESULT ipo_supported OUTPUT ipo_error)

if (ipo_supported)
    set_property(TARGET FileDB PROPERTY
            INTERPROCEDURAL_OPTIMIZATION_RELEASE TRUE
    )
endif ()
