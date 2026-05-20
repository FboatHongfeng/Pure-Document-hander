r"""Windows 右键菜单集成

通过 HKCU\Software\Classes 注册右键菜单（无需管理员权限），
提供 install / uninstall / is_installed 三个公共接口。
"""
import os
import sys
import winreg
from pathlib import Path


MENU_KEY_CONVERT = r"Software\Classes\*\shell\Pure.Convert"
MENU_KEY_COMPRESS = r"Software\Classes\*\shell\Pure.Compress"


def _get_exe_path() -> str:
    """获取当前exe路径（打包后或开发中的python路径）"""
    if getattr(sys, "frozen", False):
        return sys.executable
    return sys.executable  # python.exe（开发模式）


def _get_command(exe_path: str, action: str) -> str:
    return f'"{exe_path}" --{action} "%1"'


def install_context_menu() -> bool:
    """安装右键菜单，返回是否成功"""
    exe_path = _get_exe_path()
    try:
        # 转换菜单
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, MENU_KEY_CONVERT)
        winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, "通过 Pure 转换")
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, exe_path)
        winreg.SetValueEx(key, "Position", 0, winreg.REG_SZ, "middle")
        cmd_key = winreg.CreateKey(key, "command")
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, _get_command(exe_path, "convert"))
        winreg.CloseKey(cmd_key)
        winreg.CloseKey(key)

        # 压缩菜单
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, MENU_KEY_COMPRESS)
        winreg.SetValueEx(key, "MUIVerb", 0, winreg.REG_SZ, "通过 Pure 压缩")
        winreg.SetValueEx(key, "Icon", 0, winreg.REG_SZ, exe_path)
        winreg.SetValueEx(key, "Position", 0, winreg.REG_SZ, "middle")
        cmd_key = winreg.CreateKey(key, "command")
        winreg.SetValueEx(cmd_key, "", 0, winreg.REG_SZ, _get_command(exe_path, "compress"))
        winreg.CloseKey(cmd_key)
        winreg.CloseKey(key)

        return True
    except Exception as e:
        print(f"注册右键菜单失败: {e}")
        return False


def uninstall_context_menu() -> bool:
    """卸载右键菜单"""
    try:
        for menu_key in [MENU_KEY_CONVERT, MENU_KEY_COMPRESS]:
            try:
                key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, menu_key + r"\command")
                winreg.CloseKey(key)
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, menu_key + r"\command")
            except FileNotFoundError:
                pass
            try:
                winreg.DeleteKey(winreg.HKEY_CURRENT_USER, menu_key)
            except FileNotFoundError:
                pass
        return True
    except Exception as e:
        print(f"卸载右键菜单失败: {e}")
        return False


def is_context_menu_installed() -> bool:
    """检查右键菜单是否已安装"""
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, MENU_KEY_CONVERT)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
