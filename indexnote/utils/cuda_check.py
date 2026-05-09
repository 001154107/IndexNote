"""
CUDA Environment Check & Auto-Repair Tool.
Verifies the presence of required NVIDIA DLLs for GPU acceleration (faster-whisper).
"""

import ctypes
import ctypes.util
import logging
import os
import platform
import subprocess
import sys

from rich.console import Console
from rich.prompt import Prompt
from rich.panel import Panel

logger = logging.getLogger(__name__)
console = Console()


def inject_pip_cuda_dlls() -> bool:
    """
    Search for NVIDIA PyPI wheels and inject their 'bin' directories into
    the current process DLL search path.
    """
    import site
    
    injected = False
    try:
        site_packages = site.getsitepackages()
        # Also check user site packages just in case
        try:
            site_packages.append(site.getusersitepackages())
        except Exception:
            pass

        for sp in site_packages:
            for pkg in ["cublas", "cudnn"]:
                bin_path = os.path.join(sp, "nvidia", pkg, "bin")
                if os.path.exists(bin_path):
                    if hasattr(os, 'add_dll_directory'):
                        os.add_dll_directory(bin_path)
                    os.environ["PATH"] = bin_path + os.pathsep + os.environ.get("PATH", "")
                    injected = True
                    logger.debug("Injected CUDA DLL path: %s", bin_path)
    except Exception as e:
        logger.warning("Failed to inject pip CUDA DLLs: %s", e)
        
    return injected


def _is_cuda_dll_available() -> bool:
    """Check if the CTranslate2 required CUDA 12 or 11 DLLs can be loaded."""
    if platform.system() != "Windows":
        return True  # Linux/macOS usually handle shared libs via LD_LIBRARY_PATH natively

    # Common required DLLs for faster-whisper/ctranslate2 on Windows
    for dll_name in ["cublas64_12.dll", "cublas64_11.dll"]:
        # Try ctypes.util first
        if ctypes.util.find_library(dll_name):
            return True
        
        # Try a direct load attempt (will search PATH and os.add_dll_directory)
        try:
            ctypes.CDLL(dll_name)
            return True
        except OSError:
            pass
            
    return False


def _auto_install_pypi_cuda() -> bool:
    """Run pip to install the NVIDIA CUDA/cuDNN wheels."""
    console.print("[cyan]Installing NVIDIA CUDA wheels via pip (this may take a minute)...[/cyan]")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", 
            "nvidia-cublas-cu12", "nvidia-cudnn-cu12"
        ])
        
        # Inject them immediately for this session
        inject_pip_cuda_dlls()
        return True
    except subprocess.CalledProcessError as e:
        console.print(f"[red]Failed to install packages: {e}[/red]")
        return False


def run_cuda_check() -> None:
    """
    Run the interactive CUDA check. 
    Should be called at application boot on the main thread.
    """
    # 1. Attempt to inject existing pip-installed DLLs (if they already did the fix)
    inject_pip_cuda_dlls()

    # 2. Check if CUDA is available
    if _is_cuda_dll_available():
        logger.info("CUDA DLLs verified successfully.")
        return

    # If not on Windows, or we just couldn't find it, we only prompt on Windows
    # because CTranslate2 pip packages on Linux usually contain what they need.
    if platform.system() != "Windows":
        logger.warning("Could not verify CUDA libraries. Hardware acceleration may fail.")
        return

    # 3. Missing DLLs on Windows. Prompt the user.
    console.print("\n")
    console.print(Panel(
        "[bold yellow]⚠️ Missing NVIDIA CUDA Libraries Detected[/bold yellow]\n\n"
        "IndexNote detected that you are missing the `cublas64_12.dll` libraries required "
        "to run audio transcription (faster-whisper) on your NVIDIA GPU.\n\n"
        "Without these, background transcription will crash or run very slowly.",
        title="Environment Check",
        border_style="yellow"
    ))

    console.print("[bold]How would you like to resolve this?[/bold]")
    console.print("  [cyan]1.[/cyan] Auto-repair via pip (Installs NVIDIA DLLs securely into Python)")
    console.print("  [cyan]2.[/cyan] Provide me the official NVIDIA Toolkit download links")
    console.print("  [cyan]3.[/cyan] Ignore and force transcription to use the CPU (Slower)")

    while True:
        choice = Prompt.ask("Select an option", choices=["1", "2", "3"])
        
        if choice == "1":
            success = _auto_install_pypi_cuda()
            if success and _is_cuda_dll_available():
                console.print("[green]✅ Successfully repaired CUDA dependencies![/green]\n")
                break
            else:
                console.print("[yellow]Auto-repair failed or DLLs still missing. Defaulting to CPU.[/yellow]\n")
                os.environ["INDEXNOTE_FORCE_CPU"] = "1"
                break
                
        elif choice == "2":
            console.print("\n[bold]Official NVIDIA Downloads:[/bold]")
            console.print("1. CUDA Toolkit: https://developer.nvidia.com/cuda-downloads?target_os=Windows")
            console.print("2. cuDNN: https://developer.nvidia.com/cudnn-downloads")
            console.print("\n[dim]Install these system-wide, restart your PC, and IndexNote will use them automatically.[/dim]")
            console.print("[yellow]Defaulting to CPU for this session...[/yellow]\n")
            os.environ["INDEXNOTE_FORCE_CPU"] = "1"
            break
            
        elif choice == "3":
            console.print("[yellow]Defaulting to CPU transcription for this session...[/yellow]\n")
            os.environ["INDEXNOTE_FORCE_CPU"] = "1"
            break
