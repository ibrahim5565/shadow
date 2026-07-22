"""
GPU Benchmark - Tests PyTorch GPU performance
"""
import torch
import time
import sys

print("="*70)
print("AEGIS GOLD — GPU BENCHMARK TEST")
print("="*70)

# Check CUDA availability
if not torch.cuda.is_available():
    print("❌ CUDA not available!")
    print("GPU training will NOT work.")
    sys.exit(1)

print(f"✅ CUDA Available: {torch.cuda.is_available()}")
print(f"✅ PyTorch Version: {torch.__version__}")
print(f"✅ CUDA Version: {torch.version.cuda}")
print(f"✅ GPU Name: {torch.cuda.get_device_name(0)}")
print(f"✅ GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
print(f"✅ cuDNN Enabled: {torch.backends.cudnn.enabled}")
print("="*70)

# Benchmark: Matrix multiplication
print("\nRunning GPU Performance Test...")
print("─"*70)

# Small test (warm up)
device = torch.device('cuda')
x = torch.randn(1000, 1000, device=device)
y = torch.randn(1000, 1000, device=device)
_ = torch.matmul(x, y)
torch.cuda.synchronize()
print("✅ GPU warm-up complete")

# Actual benchmark
sizes = [1000, 2000, 4000]
print("\nMatrix Multiplication Benchmark:")
print(f"{'Size':<10} {'GPU Time (ms)':<15} {'Operations/sec':<20}")
print("─"*70)

for size in sizes:
    # CPU benchmark
    x_cpu = torch.randn(size, size)
    y_cpu = torch.randn(size, size)
    
    start = time.time()
    for _ in range(10):
        _ = torch.matmul(x_cpu, y_cpu)
    cpu_time = (time.time() - start) * 100  # Convert to ms
    
    # GPU benchmark
    x_gpu = torch.randn(size, size, device=device)
    y_gpu = torch.randn(size, size, device=device)
    
    torch.cuda.synchronize()
    start = time.time()
    for _ in range(10):
        _ = torch.matmul(x_gpu, y_gpu)
    torch.cuda.synchronize()
    gpu_time = (time.time() - start) * 100  # Convert to ms
    
    ops_per_sec = (10 * size * size * size) / (gpu_time / 1000) / 1e9
    speedup = cpu_time / gpu_time
    
    print(f"{size:<10} {gpu_time:<15.2f} {ops_per_sec:<20.2f} GFLOPS")
    print(f"           CPU: {cpu_time:.2f}ms | Speedup: {speedup:.1f}x faster")

# Neural network training benchmark
print("\n" + "="*70)
print("Neural Network Training Benchmark:")
print("─"*70)

# Simple model
model = torch.nn.Sequential(
    torch.nn.Linear(256, 512),
    torch.nn.ReLU(),
    torch.nn.Linear(512, 256),
    torch.nn.ReLU(),
    torch.nn.Linear(256, 128),
).to(device)

optimizer = torch.optim.Adam(model.parameters())
criterion = torch.nn.MSELoss()

# Training loop
batch_size = 32
num_epochs = 50

x_train = torch.randn(batch_size, 256, device=device)
y_train = torch.randn(batch_size, 128, device=device)

torch.cuda.synchronize()
start = time.time()

for epoch in range(num_epochs):
    optimizer.zero_grad()
    output = model(x_train)
    loss = criterion(output, y_train)
    loss.backward()
    optimizer.step()

torch.cuda.synchronize()
gpu_train_time = (time.time() - start) * 1000  # ms

epochs_per_sec = num_epochs / (gpu_train_time / 1000)

print(f"✅ Training Time: {gpu_train_time:.2f}ms for {num_epochs} epochs")
print(f"✅ Speed: {epochs_per_sec:.1f} epochs/second")
print(f"✅ Average: {gpu_train_time/num_epochs:.2f}ms per epoch")

# Memory info
print("\n" + "="*70)
print("GPU Memory Usage:")
print("─"*70)
print(f"Allocated: {torch.cuda.memory_allocated(0) / 1024**2:.2f} MB")
print(f"Cached: {torch.cuda.memory_reserved(0) / 1024**2:.2f} MB")
print(f"Available: {(torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated(0)) / 1024**2:.2f} MB")

print("\n" + "="*70)
print("✅ GPU BENCHMARK COMPLETE")
print("="*70)
print("\nYour GPU is ready for training!")
print(f"Expected speedup for model training: 10-20x faster than CPU")
print("\nRecommended commands:")
print("  • Train all models: python TRAIN_ALL_MODELS.py")
print("  • Monitor GPU: nvidia-smi -l 1")
