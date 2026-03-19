# 运行和开发环境配置

语言选择：[English](./environment-setup.md) | [简体中文](./environment-setup_zh-Hans.md)

------

当前服务以单一后端服务运行，运行环境要求如下：

后端服务：
- 系统要求：
- - **Linux**: x86_64 + ARM64 架构，建议 Ubuntu 22.04 及以上 LTS 版本
- - **Windows**: **WSL2** 下 x86_64 + ARM64 架构，建议 Windows11 22H2 及以上版本
- - **macOS**: x86_64 + ARM64 架构

本地视觉模型宿主机（可选）：
- 额外要求：
- - **Linux**：如需运行本地视觉模型，建议使用 x86_64 架构
- - **Windows**：如需运行本地视觉模型，建议在 **WSL2** 下使用 x86_64 架构
- - **macOS**：是否支持取决于所选本地模型与运行时
- 显卡要求：
- - **NVIDIA**：建议30系及以上显卡，显存8G及以上；显卡驱动版本527.41及以上；CUDA版本12.5.1及以上
- - 其他加速器：请根据你计划使用的本地模型与运行时自行确认兼容性

软件要求
- **Python**: Python 3.10及以上
- **Docker**: 20.10 及以上版本，要求支持 `docker compose`

## 环境配置

> 📄**NOTICE:**
>
> - 采用 Docker 方法运行，请按照下述步骤安装环境，如果环境已安装且验证无问题，可跳过环境配置步骤，否则可能导致程序无法运行
>
> - Windows 环境需要注意：
>   - 摄像头只允许局域网拉流，Windows 下需要将 WSL2 的网络模式设置为 **Mirrored**
>   - WSL2 网络设置为 **Mirrored** 模式后，注意配置Hyper-V防火墙允许入站连接；重新刷新摄像头列表，如果还是离线状态，可以尝试关闭Windows防火墙
> - macOS 环境需要注意：
>   - macOS 使用 Docker 运行本服务，需要配置好虚拟机网络为**桥接模式**（可参考下述教程），否则无法拉流；
>   - Docker Desktop 的网络模式默认为 NAT 模式，通过 Docker Desktop 运行服务将无法拉流，可自行配置为桥接模式或者参考下述教程配置
>   - 建议使用有线网卡桥接，原因是macOS 的 Wi-Fi 硬件驱动（以及大多数无线接入点）不允许同一个 Wi-Fi 链接上有两个不同的 MAC 地址（一个是你的 Mac，一个是虚拟机）

### Linux

Linux 环境配置可参考：[English](./environment-setup-linux.md) | [简体中文](./environment-setup-linux_zh-Hans.md)

### Windows

Windows 环境配置可参考：[English](./environment-setup-windows.md) | [简体中文](./environment-setup-windows_zh-Hans.md)

### macOS（M 系列和 Intel 系列）

macOS 环境配置可参考：[English](./environment-setup-macos.md) | [简体中文](./environment-setup-macos_zh-Hans.md)

## 下载模型

下述所有操作都在`models`文件下进行。

### Xiaomi MiMo-VL-Miloco-7B

小米自研的多模态模型，用于图像的本地推理。

模型下载地址：

- `huggingface`:
- - 量化: https://huggingface.co/xiaomi-open-source/Xiaomi-MiMo-VL-Miloco-7B-GGUF
- - 未量化: https://huggingface.co/xiaomi-open-source/Xiaomi-MiMo-VL-Miloco-7B

- `modelscope`:
- - 量化: https://modelscope.cn/models/xiaomi-open-source/Xiaomi-MiMo-VL-Miloco-7B-GGUF
- - 未量化: https://modelscope.cn/models/xiaomi-open-source/Xiaomi-MiMo-VL-Miloco-7B

在`models`文件夹下，新建目录`MiMo-VL-Miloco-7B`，然后打开`modelspace`量化模型下载链接：

- 下载`MiMo-VL-Miloco-7B_Q4_0.gguf`放到`MiMo-VL-Miloco-7B`目录下
- 下载`mmproj-MiMo-VL-Miloco-7B_BF16.gguf`放到`MiMo-VL-Miloco-7B`目录下

### Qwen3-8B

如果机器显存够，也可以继续下载本地的规划模型，规划模型可以使用`Qwen-8B`模型，通过修改配置文件，也可以使用其它模型。

模型下载地址：

- `huggingface`：https://huggingface.co/Qwen/Qwen3-8B
- `modelscope`: https://modelscope.cn/models/Qwen/Qwen3-8B-GGUF/files

在`models`文件夹下，新建`Qwen3-8B`目录，然后打开上述下载链接，下载 Q4 量化版本即可：

- 下载`Qwen3-8B-Q4_K_M.gguf`放到`Qwen3-8B`目录下

## 运行

使用`docker compose`运行程序，复制`.env.example`，命名为`.env`，端口根据实际环境修改。

运行程序：

```Shell
# Pull 镜像
docker compose pull
# 卸载
docker compose down
# 启动
docker compose up -d
```

后端容器默认使用 `MILOCO_AGENT_RUNTIME_BACKEND=auto`。如果镜像内已安装 `miloco-agent-runtime` 原生 wheel，则优先使用 Rust Runtime；如果 wheel 不存在，则自动回退到 Python Runtime。

如需在构建镜像时固定某个 release 的 wheel，可传入以下构建参数之一：

```Shell
MILOCO_AGENT_RUNTIME_VERSION=<release-tag>
MILOCO_AGENT_RUNTIME_WHEEL_URL=<direct-wheel-url>
```

## 访问服务

通过`https://<your ip>:8000`访问服务，如果是本机访问， IP 为`127.0.0.1`；

> 📄NOTICE:
>
> - 请使用 **https** 访问，而不是 **http**
> - Windows 下，在 Windows 中可以尝试直接访问 WSL 的 IP 地址，如 `https://<wsl ip>:8000`
> - macOS 环境下，如果网络模式配置为桥接模式，访问时请使用 Docker 所在虚拟机的 IP。
