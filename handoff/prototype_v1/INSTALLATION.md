# Installation

Python target: 3.12.5.

Create an environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
```

Install PyTorch and Torchvision using the official selector:

```text
https://pytorch.org/get-started/locally/
```

Select PyTorch 2.8.0, Torchvision 0.23.0 and the CUDA build that matches the target driver/runtime. Do not assume CUDA wheels can be installed from the default PyPI index.

Install repository runtime packages:

```powershell
python -m pip install -r .\InstallKit\requirements-model-common.txt
```

For CUDA deployments, review `InstallKit/requirements-model-cuda.txt` and use the official PyTorch selector command.
