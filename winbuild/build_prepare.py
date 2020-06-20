import os
import shutil
import struct
import subprocess
import sys


def cmd_cd(path):
    return "cd /D {path}".format(**locals())


def cmd_set(name, value):
    return "set {name}={value}".format(**locals())


def cmd_append(name, value):
    op = "path " if name == "PATH" else "set {name}="
    return (op + "%{name}%;{value}").format(**locals())


def cmd_copy(src, tgt):
    return 'copy /Y /B "{src}" "{tgt}"'.format(**locals())


def cmd_xcopy(src, tgt):
    return 'xcopy /Y /E "{src}" "{tgt}"'.format(**locals())


def cmd_mkdir(path):
    return 'mkdir "{path}"'.format(**locals())


def cmd_rmdir(path):
    return 'rmdir /S /Q "{path}"'.format(**locals())


def cmd_nmake(makefile=None, target="", params=None):
    if params is None:
        params = ""
    elif isinstance(params, list) or isinstance(params, tuple):
        params = " ".join(params)
    else:
        params = str(params)

    return " ".join(
        [
            "{{nmake}}",
            "-nologo",
            '-f "{makefile}"' if makefile is not None else "",
            "{params}",
            '"{target}"',
        ]
    ).format(**locals())


def cmd_cmake(params=None, file="."):
    if params is None:
        params = ""
    elif isinstance(params, list) or isinstance(params, tuple):
        params = " ".join(params)
    else:
        params = str(params)
    return " ".join(
        [
            "{{cmake}}",
            "-DCMAKE_VERBOSE_MAKEFILE=ON",
            "-DCMAKE_RULE_MESSAGES:BOOL=OFF",
            "-DCMAKE_BUILD_TYPE=Release",
            "{params}",
            '-G "NMake Makefiles"',
            '"{file}"',
        ]
    ).format(**locals())


def cmd_msbuild(
    file, configuration="Release", target="Build", platform="{msbuild_arch}"
):
    return " ".join(
        [
            "{{msbuild}}",
            "{file}",
            '/t:"{target}"',
            '/p:Configuration="{configuration}"',
            "/p:Platform={platform}",
            "/m",
        ]
    ).format(**locals())


SF_MIRROR = "http://iweb.dl.sourceforge.net"

architectures = {
    "x86": {"vcvars_arch": "x86", "msbuild_arch": "Win32"},
    "x64": {"vcvars_arch": "x86_amd64", "msbuild_arch": "x64"},
}

header = [
    cmd_set("INCLUDE", "{inc_dir}"),
    cmd_set("INCLIB", "{lib_dir}"),
    cmd_set("LIB", "{lib_dir}"),
    cmd_append("PATH", "{bin_dir}"),
]

# dependencies, listed in order of compilation
deps = {
    "libjpeg": {
        "url": SF_MIRROR + "/project/libjpeg-turbo/2.0.4/libjpeg-turbo-2.0.4.tar.gz",
        "filename": "libjpeg-turbo-2.0.4.tar.gz",
        "dir": "libjpeg-turbo-2.0.4",
        "build": [
            cmd_cmake(
                [
                    "-DENABLE_SHARED:BOOL=FALSE",
                    "-DWITH_JPEG8:BOOL=TRUE",
                    "-DWITH_CRT_DLL:BOOL=TRUE",
                ]
            ),
            cmd_nmake(target="clean"),
            cmd_nmake(target="jpeg-static"),
            cmd_copy("jpeg-static.lib", "libjpeg.lib"),
            cmd_nmake(target="cjpeg-static"),
            cmd_copy("cjpeg-static.exe", "cjpeg.exe"),
            cmd_nmake(target="djpeg-static"),
            cmd_copy("djpeg-static.exe", "djpeg.exe"),
        ],
        "headers": ["j*.h"],
        "libs": ["libjpeg.lib"],
        "bins": ["cjpeg.exe", "djpeg.exe"],
    },
    "zlib": {
        "url": "http://zlib.net/zlib1211.zip",
        "filename": "zlib1211.zip",
        "dir": "zlib-1.2.11",
        "build": [
            cmd_nmake(r"win32\Makefile.msc", "clean"),
            cmd_nmake(r"win32\Makefile.msc", "zlib.lib"),
            cmd_copy("zlib.lib", "z.lib"),
        ],
        "headers": [r"z*.h"],
        "libs": [r"*.lib"],
    },
    "libtiff": {
        "url": "https://download.osgeo.org/libtiff/tiff-4.1.0.tar.gz",
        "filename": "tiff-4.1.0.tar.gz",
        "dir": "tiff-4.1.0",
        "build": [
            cmd_copy(r"{winbuild_dir}\tiff.opt", "nmake.opt"),
            cmd_nmake("makefile.vc", "clean"),
            cmd_nmake("makefile.vc", "lib"),
        ],
        "headers": [r"libtiff\tiff*.h"],
        "libs": [r"libtiff\*.lib"],
        # "bins": [r"libtiff\*.dll"],
    },
    "libwebp": {
        "url": "http://downloads.webmproject.org/releases/webp/libwebp-1.1.0.tar.gz",
        "filename": "libwebp-1.1.0.tar.gz",
        "dir": "libwebp-1.1.0",
        "build": [
            cmd_rmdir(r"output\release-static"),  # clean
            cmd_nmake(
                "Makefile.vc",
                "all",
                ["CFG=release-static", "OBJDIR=output", "ARCH={architecture}"],
            ),
            cmd_mkdir(r"{inc_dir}\webp"),
            cmd_copy(r"src\webp\*.h", r"{inc_dir}\webp"),
        ],
        "libs": [r"output\release-static\{architecture}\lib\*.lib"],
    },
    "freetype": {
        "url": "https://download.savannah.gnu.org/releases/freetype/freetype-2.10.2.tar.gz",  # noqa: E501
        "filename": "freetype-2.10.2.tar.gz",
        "dir": "freetype-2.10.2",
        "patch": {
            r"builds\windows\vc2010\freetype.vcxproj": {
                # freetype setting is /MD for .dll and /MT for .lib, we need /MD
                "<RuntimeLibrary>MultiThreaded</RuntimeLibrary>": "<RuntimeLibrary>MultiThreadedDLL</RuntimeLibrary>",  # noqa: E501
                # freetype doesn't specify SDK version, MSBuild may guess incorrectly
                '<PropertyGroup Label="Globals">': '<PropertyGroup Label="Globals">\n    <WindowsTargetPlatformVersion>$(WindowsSDKVersion)</WindowsTargetPlatformVersion>',  # noqa: E501
            }
        },
        "build": [
            cmd_rmdir("objs"),
            cmd_msbuild(
                r"builds\windows\vc2010\freetype.sln", "Release Static", "Clean"
            ),
            cmd_msbuild(
                r"builds\windows\vc2010\freetype.sln", "Release Static", "Build"
            ),
            cmd_xcopy("include", "{inc_dir}"),
        ],
        "libs": [r"objs\{msbuild_arch}\Release Static\freetype.lib"],
        # "bins": [r"objs\{msbuild_arch}\Release\freetype.dll"],
    },
    "lcms2": {
        "url": SF_MIRROR + "/project/lcms/lcms/2.10/lcms2-2.10.tar.gz",
        "filename": "lcms2-2.10.tar.gz",
        "dir": "lcms2-2.10",
        "patch": {
            r"Projects\VC2017\lcms2_static\lcms2_static.vcxproj": {
                # default is /MD for x86 and /MT for x64, we need /MD always
                "<RuntimeLibrary>MultiThreaded</RuntimeLibrary>": "<RuntimeLibrary>MultiThreadedDLL</RuntimeLibrary>",  # noqa: E501
                # retarget to default toolset (selected by vcvarsall.bat)
                "<PlatformToolset>v141</PlatformToolset>": "<PlatformToolset>$(DefaultPlatformToolset)</PlatformToolset>",  # noqa: E501
                # retarget to latest (selected by vcvarsall.bat)
                "<WindowsTargetPlatformVersion>8.1</WindowsTargetPlatformVersion>": "<WindowsTargetPlatformVersion>$(WindowsSDKVersion)</WindowsTargetPlatformVersion>",  # noqa: E501
            }
        },
        "build": [
            cmd_rmdir("Lib"),
            cmd_rmdir(r"Projects\VC2017\Release"),
            cmd_msbuild(r"Projects\VC2017\lcms2.sln", "Release", "Clean"),
            cmd_msbuild(r"Projects\VC2017\lcms2.sln", "Release", "lcms2_static"),
            cmd_xcopy("include", "{inc_dir}"),
        ],
        "libs": [r"Lib\MS\*.lib"],
    },
    "openjpeg": {
        "url": "https://github.com/uclouvain/openjpeg/archive/v2.3.1.tar.gz",
        "filename": "openjpeg-2.3.1.tar.gz",
        "dir": "openjpeg-2.3.1",
        "build": [
            cmd_cmake(("-DBUILD_THIRDPARTY:BOOL=OFF", "-DBUILD_SHARED_LIBS:BOOL=OFF")),
            cmd_nmake(target="clean"),
            cmd_nmake(target="openjp2"),
            cmd_mkdir(r"{inc_dir}\openjpeg-2.3.1"),
            cmd_copy(r"src\lib\openjp2\*.h", r"{inc_dir}\openjpeg-2.3.1"),
        ],
        "libs": [r"bin\*.lib"],
    },
    "libimagequant": {
        # e5d454b: Merge tag '2.12.6' into msvc
        "url": "https://github.com/ImageOptim/libimagequant/archive/e5d454bc7f5eb63ee50c84a83a7fa5ac94f68ec4.zip",  # noqa: E501
        "filename": "libimagequant-e5d454bc7f5eb63ee50c84a83a7fa5ac94f68ec4.zip",
        "dir": "libimagequant-e5d454bc7f5eb63ee50c84a83a7fa5ac94f68ec4",
        "patch": {
            "CMakeLists.txt": {
                "add_library": "add_compile_options(-openmp-)\r\nadd_library",
                " SHARED": " STATIC",
            }
        },
        "build": [
            # lint: do not inline
            cmd_cmake(),
            cmd_nmake(target="clean"),
            cmd_nmake(),
        ],
        "headers": [r"*.h"],
        "libs": [r"*.lib"],
    },
    "harfbuzz": {
        "url": "https://github.com/harfbuzz/harfbuzz/archive/2.6.7.zip",
        "filename": "harfbuzz-2.6.7.zip",
        "dir": "harfbuzz-2.6.7",
        "build": [
            cmd_cmake("-DHB_HAVE_FREETYPE:BOOL=TRUE"),
            cmd_nmake(target="clean"),
            cmd_nmake(target="harfbuzz"),
        ],
        "headers": [r"src\*.h"],
        "libs": [r"*.lib"],
    },
    "fribidi": {
        "url": "https://github.com/fribidi/fribidi/archive/v1.0.9.zip",
        "filename": "fribidi-1.0.9.zip",
        "dir": "fribidi-1.0.9",
        "build": [
            cmd_copy(r"{winbuild_dir}\fribidi.cmake", r"CMakeLists.txt"),
            cmd_cmake(),
            cmd_nmake(target="clean"),
            cmd_nmake(target="fribidi"),
        ],
        "headers": [r"lib\*.h"],
        "libs": [r"*.lib"],
    },
    "libraqm": {
        "url": "https://github.com/HOST-Oman/libraqm/archive/v0.7.0.zip",
        "filename": "libraqm-0.7.0.zip",
        "dir": "libraqm-0.7.0",
        "build": [
            cmd_copy(r"{winbuild_dir}\raqm.cmake", r"CMakeLists.txt"),
            cmd_cmake(),
            cmd_nmake(target="clean"),
            cmd_nmake(target="libraqm"),
        ],
        "headers": [r"src\*.h"],
        "bins": [r"libraqm.dll"],
    },
}


# based on distutils._msvccompiler from CPython 3.7.4
def find_msvs():
    root = os.environ.get("ProgramFiles(x86)") or os.environ.get("ProgramFiles")
    if not root:
        print("Program Files not found")
        return None

    try:
        vspath = (
            subprocess.check_output(
                [
                    os.path.join(
                        root, "Microsoft Visual Studio", "Installer", "vswhere.exe"
                    ),
                    "-latest",
                    "-prerelease",
                    "-requires",
                    "Microsoft.VisualStudio.Component.VC.Tools.x86.x64",
                    "-property",
                    "installationPath",
                    "-products",
                    "*",
                ]
            )
            .decode(encoding="mbcs")
            .strip()
        )
    except (subprocess.CalledProcessError, OSError, UnicodeDecodeError):
        print("vswhere not found")
        return None

    if not os.path.isdir(os.path.join(vspath, "VC", "Auxiliary", "Build")):
        print("Visual Studio seems to be missing C compiler")
        return None

    vs = {
        "header": [],
        # nmake selected by vcvarsall
        "nmake": "nmake.exe",
        "vs_dir": vspath,
    }

    # vs2017
    msbuild = os.path.join(vspath, "MSBuild", "15.0", "Bin", "MSBuild.exe")
    if os.path.isfile(msbuild):
        vs["msbuild"] = '"{}"'.format(msbuild)
    else:
        # vs2019
        msbuild = os.path.join(vspath, "MSBuild", "Current", "Bin", "MSBuild.exe")
        if os.path.isfile(msbuild):
            vs["msbuild"] = '"{}"'.format(msbuild)
        else:
            print("Visual Studio MSBuild not found")
            return None

    vcvarsall = os.path.join(vspath, "VC", "Auxiliary", "Build", "vcvarsall.bat")
    if not os.path.isfile(vcvarsall):
        print("Visual Studio vcvarsall not found")
        return None
    vs["header"].append('call "{}" {{vcvars_arch}}'.format(vcvarsall))

    return vs


def extract_dep(url, filename):
    import urllib.request
    import tarfile
    import zipfile

    file = os.path.join(depends_dir, filename)
    if not os.path.exists(file):
        ex = None
        for i in range(3):
            try:
                print("Fetching %s (attempt %d)..." % (url, i + 1))
                content = urllib.request.urlopen(url).read()
                with open(file, "wb") as f:
                    f.write(content)
                break
            except urllib.error.URLError as e:
                ex = e
        else:
            raise RuntimeError(ex)

    print("Extracting " + filename)
    if filename.endswith(".zip"):
        with zipfile.ZipFile(file) as zf:
            zf.extractall(build_dir)
    elif filename.endswith(".tar.gz") or filename.endswith(".tgz"):
        with tarfile.open(file, "r:gz") as tgz:
            tgz.extractall(build_dir)
    else:
        raise RuntimeError("Unknown archive type: " + filename)


def write_script(name, lines):
    name = os.path.join(build_dir, name)
    lines = [line.format(**prefs) for line in lines]
    print("Writing " + name)
    with open(name, "w") as f:
        f.write("\n\r".join(lines))
    if verbose:
        for line in lines:
            print("    " + line)


def get_footer(dep):
    lines = []
    for out in dep.get("headers", []):
        lines.append(cmd_copy(out, "{inc_dir}"))
    for out in dep.get("libs", []):
        lines.append(cmd_copy(out, "{lib_dir}"))
    for out in dep.get("bins", []):
        lines.append(cmd_copy(out, "{bin_dir}"))
    return lines


def build_dep(name):
    dep = deps[name]
    dir = dep["dir"]
    file = "build_dep_{name}.cmd".format(**locals())

    extract_dep(dep["url"], dep["filename"])

    for patch_file, patch_list in dep.get("patch", {}).items():
        patch_file = os.path.join(build_dir, dir, patch_file.format(**prefs))
        with open(patch_file, "r") as f:
            text = f.read()
        for patch_from, patch_to in patch_list.items():
            text = text.replace(patch_from.format(**prefs), patch_to.format(**prefs))
        with open(patch_file, "w") as f:
            f.write(text)

    banner = "Building {name} ({dir})".format(**locals())
    lines = [
        "@echo " + ("=" * 70),
        "@echo ==== {:<60} ====".format(banner),
        "@echo " + ("=" * 70),
        "cd /D %s" % os.path.join(build_dir, dir),
        *prefs["header"],
        *dep.get("build", []),
        *get_footer(dep),
    ]

    write_script(file, lines)
    return file


def build_dep_all():
    lines = ["@echo on"]
    for dep_name in deps:
        if dep_name in disabled:
            continue
        lines.append(r'cmd.exe /c "{{build_dir}}\{}"'.format(build_dep(dep_name)))
        lines.append("if errorlevel 1 echo Build failed! && exit /B 1")
    lines.append("@echo All Pillow dependencies built successfully!")
    write_script("build_dep_all.cmd", lines)


def build_pillow():
    lines = [
        "@echo ---- Building Pillow (build_ext %*) ----",
        cmd_cd("{pillow_dir}"),
        *prefs["header"],
        cmd_set("DISTUTILS_USE_SDK", "1"),  # use same compiler to build Pillow
        cmd_set("MSSdk", "1"),  # for Python 3.5 and PyPy3.6
        cmd_set("py_vcruntime_redist", "true"),  # use /MD, not /MT
        r'"{python_dir}\{python_exe}" setup.py build_ext %*',
    ]

    write_script("build_pillow.cmd", lines)


if __name__ == "__main__":
    # winbuild directory
    winbuild_dir = os.path.dirname(os.path.realpath(__file__))

    verbose = False
    disabled = []
    depends_dir = os.environ.get("PILLOW_DEPS", os.path.join(winbuild_dir, "depends"))
    python_dir = os.environ.get("PYTHON")
    python_exe = os.environ.get("EXECUTABLE", "python.exe")
    architecture = os.environ.get(
        "ARCHITECTURE", "x86" if struct.calcsize("P") == 4 else "x64"
    )
    build_dir = os.environ.get("PILLOW_BUILD", os.path.join(winbuild_dir, "build"))
    for arg in sys.argv[1:]:
        if arg == "-v":
            verbose = True
        elif arg == "--no-imagequant":
            disabled += ["libimagequant"]
        elif arg == "--no-raqm":
            disabled += ["harfbuzz", "fribidi", "libraqm"]
        elif arg.startswith("--depends="):
            depends_dir = arg[10:]
        elif arg.startswith("--python="):
            python_dir = arg[9:]
        elif arg.startswith("--executable="):
            python_exe = arg[13:]
        elif arg.startswith("--architecture="):
            architecture = arg[15:]
        elif arg.startswith("--dir="):
            build_dir = arg[6:]
        else:
            raise ValueError("Unknown parameter: " + arg)

    # dependency cache directory
    os.makedirs(depends_dir, exist_ok=True)
    print("Caching dependencies in:", depends_dir)

    if python_dir is None:
        python_dir = os.path.dirname(os.path.realpath(sys.executable))
        python_exe = os.path.basename(sys.executable)
    print("Target Python:", os.path.join(python_dir, python_exe))

    arch_prefs = architectures[architecture]
    print("Target Architecture:", architecture)

    msvs = find_msvs()
    if msvs is None:
        raise RuntimeError(
            "Visual Studio not found. Please install Visual Studio 2017 or newer."
        )
    print("Found Visual Studio at:", msvs["vs_dir"])

    print("Using output directory:", build_dir)

    # build directory for *.h files
    inc_dir = os.path.join(build_dir, "inc")
    # build directory for *.lib files
    lib_dir = os.path.join(build_dir, "lib")
    # build directory for *.bin files
    bin_dir = os.path.join(build_dir, "bin")

    shutil.rmtree(build_dir, ignore_errors=True)
    for path in [build_dir, inc_dir, lib_dir, bin_dir]:
        os.makedirs(path)

    prefs = {
        # Python paths / preferences
        "python_dir": python_dir,
        "python_exe": python_exe,
        "architecture": architecture,
        **arch_prefs,
        # Pillow paths
        "pillow_dir": os.path.realpath(os.path.join(winbuild_dir, "..")),
        "winbuild_dir": winbuild_dir,
        # Build paths
        "build_dir": build_dir,
        "inc_dir": inc_dir,
        "lib_dir": lib_dir,
        "bin_dir": bin_dir,
        # Compilers / Tools
        **msvs,
        "cmake": "cmake.exe",  # TODO find CMAKE automatically
        # TODO find NASM automatically
        # script header
        "header": sum([header, msvs["header"], ["@echo on"]], []),
    }

    print()

    build_dep_all()
    build_pillow()
