# Mitral Valve Segmentation Using U-Net Architecture

This repository contains the implementation of my final project for the course "Advanced Machine Learning" taught by Prof. Joachim M. Buhmann at ETH Zurich. The project focuses on **automated mitral valve segmentation from ultrasound echocardiography videos** using deep learning techniques.

## Project Overview

The mitral valve is a crucial cardiac structure, and its accurate segmentation from ultrasound images is essential for cardiac diagnosis and monitoring. This project implements a U-Net-based deep learning approach to automatically segment mitral valve regions from apical four-chamber (A4C) view echocardiography videos.

### Key Features
- **Dual-task architecture**: Simultaneous bounding box detection and mitral valve segmentation
- **Advanced data augmentation**: Elastic deformation, rotation, and intensity variations
- **Custom loss functions**: IoU-based losses optimized for medical image segmentation
- **Multi-scale U-Net variants**: Specialized architectures for different segmentation tasks
- **End-to-end pipeline**: From raw ultrasound videos to final segmentation masks

## Results

Below you can see the final prediction video showing the segmentation results on test data:

![Mitral Valve Segmentation](mitral_valve_segmentation.gif)

The model achieves competitive performance with IoU scores reaching up to **0.77** on validation data for mitral valve separation tasks.

## Technical Architecture

### Model Architecture
The project implements three specialized U-Net variants:

1. **UNet_seg**: Dedicated mitral valve segmentation network
   - 5-layer encoder-decoder with skip connections
   - Configurable channel reduction factor for model efficiency
   - Optimized for pixel-level mitral valve boundary detection

2. **UNet_box**: Bounding box detection network
   - Similar architecture to UNet_seg but optimized for coarse localization
   - Provides region-of-interest constraints for the segmentation network

3. **Combined UNet**: Unified architecture for simultaneous box detection and segmentation

### Data Preprocessing & Augmentation
- **Elastic deformation**: Random grid-based deformation with configurable sigma and rotation
- **Geometric augmentations**: 180-degree rotations with 70% probability
- **Intensity variations**: Grayscale normalization with random scaling (0.51-1.2x)
- **Multi-scale training**: Bicubic interpolation to 512×512 resolution
- **Data augmentation pipeline**: Generates 45 augmented versions per expert-annotated sample

### Loss Functions
- **IoU Loss**: Intersection over Union loss for pixel-wise optimization
- **Median IoU Loss**: Robust variant using median instead of mean across batches
- **Combined Loss**: Weighted combination for multi-task learning

## Repository Structure

### Core Implementation Files
```
├── model_2.py              # U-Net architecture implementations (UNet, UNet_seg, UNet_box)
├── train.py                # Training pipeline with validation and IoU evaluation
├── predict.py              # Inference pipeline for test data prediction
├── dataset.py              # Custom PyTorch dataset class with preprocessing
├── losses.py               # Custom loss functions (IoU, Median IoU)
├── utility.py              # Utility functions for data loading and preprocessing
├── augment_data_3.py       # Advanced data augmentation pipeline
```

### Experimental & Visualization
```
├── task3.ipynb             # Jupyter notebook for data exploration and experimentation
├── make_video_A4C_view.py  # Video generation with overlay visualization
├── convert_to_gif.py       # GIF conversion utilities
├── convert_to_gif_opencv.py # OpenCV-based GIF generation
```

### Model Performance Tracking
```
├── models_final/           # Trained model checkpoints
│   ├── separation_IoU_*.pth    # Segmentation models with IoU scores
│   └── box_IoU_*.pth          # Bounding box models with IoU scores
```

### Data Pipeline
```
├── data/                   # Training and test datasets (excluded from repo)
│   ├── train.pkl              # Original training data
│   ├── train_augmented.pkl    # Augmented training dataset
│   ├── train_augmented_veryLarge.pkl  # Extended augmentation (45x)
│   └── test.pkl               # Test dataset
```

### Outputs & Submissions
```
├── predictions/            # Model prediction outputs
├── submissions/           # Competition submission files
└── *.mp4                  # Result visualization videos
```

## Key Implementation Details

### Data Format
- **Input**: Grayscale ultrasound video frames (variable resolution)
- **Output**: Binary segmentation masks in run-length encoding (RLE) format
- **Annotation**: Expert-labeled frames with mitral valve boundaries

### Training Strategy
- **80/20 train-validation split** with random sampling
- **Batch size**: 16 with gradient accumulation
- **Optimizer**: Adam with customizable learning rate
- **Early stopping**: Based on validation IoU performance
- **Model checkpointing**: Automatic saving of best-performing models

### Evaluation Metrics
- **Intersection over Union (IoU)**: Primary evaluation metric
- **Pixel accuracy**: Secondary performance measure
- **Visual inspection**: Qualitative assessment through video overlays

## Performance Results

### Best Model Performance
- **Mitral Valve Segmentation**: IoU = 0.7685 (best checkpoint)
- **Bounding Box Detection**: IoU = 0.0140 (optimized for localization)
- **Training convergence**: Achieved within 50-100 epochs depending on augmentation level

### Model Variants Tested
- Different channel reduction factors (1x, 2x, 4x)
- Various augmentation strategies (5x, 25x, 45x multiplication)
- Combined vs. separate training for box detection and segmentation

## Requirements & Dependencies

```python
torch>=1.9.0
torchvision>=0.10.0
opencv-python>=4.5.0
matplotlib>=3.3.0
numpy>=1.20.0
scipy>=1.7.0
elasticdeform>=0.4.0
tqdm>=4.60.0
pandas>=1.3.0
```

## Usage

### Training a New Model
```python
from train import train
from model_2 import UNet_seg
from losses import IoULoss

model = UNet_seg(in_channels=1, out_channels=1, factor=1)
criterion = IoULoss()
optimizer = torch.optim.Adam(model.parameters(), lr=1e-4)

train(model=model, optimizer=optimizer, criterion=criterion, 
      epochs=100, segmentation_type="separation", 
      pkl_path="data/train_augmented_veryLarge.pkl")
```

### Running Inference
```python
from predict import generate_predictions
from model_2 import UNet_seg, UNet_box

generate_predictions(
    model_box_path="models_final/box_IoU_0.014.pth",
    model_seg_path="models_final/separation_IoU_0.7685.pth",
    test_data_path="data/test.pkl",
    output_path="predictions/final_predictions.pkl"
)
```

### Data Augmentation
```python
from augment_data_3 import augment_dataset

augment_dataset(
    data_path="data/train.pkl",
    output_path="data/train_augmented_veryLarge.pkl",
    num_augmentations=45
)
```

## Clinical Relevance

This project addresses a critical need in **cardiac imaging and diagnosis**:

- **Automated analysis**: Reduces manual annotation time for cardiologists
- **Consistent measurements**: Eliminates inter-observer variability
- **Real-time processing**: Enables rapid clinical decision-making
- **Scalable deployment**: Can be integrated into existing ultrasound systems

## Future Improvements

- **3D temporal modeling**: Incorporate temporal consistency across video frames
- **Multi-view integration**: Combine multiple echocardiography views for robust segmentation
- **Uncertainty quantification**: Add probabilistic outputs for clinical confidence estimation
- **Real-time optimization**: Model compression for real-time clinical deployment

## Acknowledgments

This project was developed as part of the Advanced Machine Learning course at ETH Zurich under the supervision of Prof. Joachim M. Buhmann. The implementation builds upon established U-Net architectures adapted for medical image segmentation tasks.

**Note**: Due to GitHub file size limitations and data privacy considerations, the following large files are excluded from this repository but were used in the project:
- Training data files (`data/` folder): `train.pkl`, `train_augmented.pkl`, `train_augmented_veryLarge.pkl`, `test.pkl`
- Model checkpoint files (`models_final/` folder): All `.pth` files containing trained model weights  
- Large video files: `da.mp4`, `final_prediction.mp4`, `final_prediction_66.mp4`, `final_prediction_99.mp4`, `output_overlay_alpha01.mp4`
- Large CSV submission files (`submissions/` folder)

The repository contains the complete source code, documentation, and an optimized GIF demonstrating the segmentation results.
