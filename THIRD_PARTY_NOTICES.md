# Third-party notices

petoken distributes or uses the following packages. Their own licenses govern those components; the repository MIT license does not replace them.

| Component | Version | License | Project |
| --- | ---: | --- | --- |
| Python | 3.13 | PSF License | https://www.python.org/ |
| Qt for Python / PySide6 Essentials / shiboken6 | 6.11.2 | LGPL-3.0-only OR GPL-2.0-only OR GPL-3.0-only (commercial alternative available) | https://www.qt.io/qt-for-python |
| UIAutomation for Windows | 2.0.29 | Apache-2.0 | https://github.com/yinkaisheng/Python-UIAutomation-for-Windows |
| pycaw | 20251023 | MIT | https://github.com/AndreMiras/pycaw |
| comtypes | 1.4.16 | MIT | https://github.com/enthought/comtypes |
| psutil | 7.2.2 | BSD-3-Clause | https://github.com/giampaolo/psutil |
| Python/WinRT projections and runtime | 3.2.1 | MIT | https://github.com/pywinrt/pywinrt |
| typing_extensions | 4.16.0 | PSF-2.0 | https://github.com/python/typing_extensions |

The Windows release uses Qt as separate dynamic libraries in the `_internal` directory so recipients can replace/relink those libraries. The corresponding Qt source and license terms are available from https://code.qt.io/cgit/pyside/pyside-setup.git/ and https://www.gnu.org/licenses/lgpl-3.0.html. Installed package license files are copied into `THIRD_PARTY_LICENSES` by `build.ps1` when available.

PyInstaller is a build-time tool and is not part of the application source license. Its bootloader distribution exception permits bundling the application; see https://pyinstaller.org/en/stable/license.html.
