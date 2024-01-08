# Nol.A-Tools

The Nol.A-Tools is a command line interface for Nol.A-SDK.
The Nol.A-SDK is a software development kit for IoT device firmware development.

## 1. Installation

### 1-1. Prerequisites

* OS: macOS, Linux, Windows (WSL2 based Linux)
* Python3

### 1-2. Install command

```
python3 -m pip install nola_tools
```

### 1-3. Update command

```
python3 -m pip install nola_tools --upgrade
```

## 2. Usage

### 2-1. Login

For private users,
```
nola login={user name}:{token}
```

### 2-2. Print information

```
nola info
```

### 2-3. Build

```
nola build
```

#### 2-3-1. Development Mode

For private users,

```
nola devmode={path to libnola source directory}
```

### 2-4. Flash

```
nola flash={options...}
```

#### 2-4-1. J-Link

To use J-Link as a flashing tool, setting ```jlink``` path variable is required.

For macOS, and Linux users,
```
nola path=jlink:{Absolute path to JLinkExe}
```

For Windows WSL2 users, the ```JLink.exe``` in the Windows region must be used.

```
nola path=jlink:/mnt/c/Program\\\ Files/SEGGER/JLink_V794/JLink.exe
```

#### 2-4-2. ST-Link

To use ST-Link as a flashing tool, setting ```stm32cube``` path variable is required.

For macOS, and Linux users,
```
nola path=jlink:{Absolute path to STM32_Programmer_CLI}
```

For Windows WSL2 users, the ```STM32_Programmer_CLI.exe``` in the Windows region must be used.
```
nola path=stm32cube:/mnt/c/Program\\\ Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe
```

### 2-5. SDK Version

#### 2-5-1. Checkout

The current and available SDK version numbers can be retrieved by using ```nola info``` command.

You can change the SDK version number like below:
```
nola checkout={new version number}
```

#### 2-5-2. Update

You can update the SDK version like below:
```
nola update
```
