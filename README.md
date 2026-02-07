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


##Create the conda environment
```bash
conda env create -f environment.yml
conda activate tarton
```

If the environment already exists and environment.yml was updated:
```bash
conda env update -f environment.yml --prune
```

## Start the Backend
```bash
conda activate tarton
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```
If successful, you should see:
```text
Uvicorn running on http://127.0.0.1:8000
```
You can test the API at:
```text
http://127.0.0.1:8000/docs
```
## Start the Frontend (Streamlit)
```bash
conda activate tarton
streamlit run frontend/app.py
```
```text
Streamlit will automatically open in your browser (default: http://localhost:8501
).
```



## Development Notes

### Python Version
- Python 3.10

### Computer Vision Stack
- PyTorch
- Ultralytics YOLO
- OpenCV

### Web Stack
- FastAPI + Uvicorn
- Streamlit

## License
This project is licensed under the MIT License.
