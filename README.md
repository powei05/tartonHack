#  Fridge

Fridge is a **computer vision + web application** that detects food items using a YOLO-based model and manages inventory through a FastAPI backend and a Streamlit frontend.

---

##  Project Structure

```text
TARTONHACK/
├── backend/                 # FastAPI backend
│   ├── main.py              # API entry point
│   ├── barcode_scanner.py   # Barcode scanning logic
│   └── requirements.txt
│
├── frontend/                # Streamlit frontend
│   ├── app.py               # UI entry point
│   └── fridge_icon.png
│
├── model/                   # Computer vision & data
│   ├── best.pt              # YOLO trained model
│   ├── vision.py            # Inference logic
│   ├── detected_food.jpg    # Example output
│   ├── inventory.json       # Inventory data
│   ├── food/                # Sample images
│   └── requirements.txt
│
├── utils/                   # Shared utilities
│
├── environment.yml          # Conda environment definition (recommended)
├── requirements.txt         # Pip dependencies (for reference / deployment)
├── README.md
└── .gitignore


**Create the conda environment**
conda env create -f environment.yml
conda activate tarton

- conda activate tarton
If the environment already exists and environment.yml was updated:
```
conda env update -f environment.yml --prune
```

**Start the Backend**
conda activate tarton
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
:: If successful, you should see:
:: Uvicorn running on http://127.0.0.1:8000

You can test the API at:

http://127.0.0.1:8000/docs


Development Notes

- Python version: 3.10

- Computer vision stack:

- PyTorch

- Ultralytics YOLO

- OpenCV

Web stack:

- FastAPI + Uvicorn

- Streamlit