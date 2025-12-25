# Nol.A-Tools

The Nol.A-Tools is a command line interface for Nol.A-SDK.
The Nol.A-SDK is a software development kit for IoT device firmware development.

- [Installation](#installation)
  * [Prerequisites](#prerequisites)
  * [Install command](#install-command)
  * [Update command](#update-command)
- [Usage](#usage)
  * [Login](#login)
  * [Print information](#print-information)
  * [Build](#build)
    + [SDK Library Development Mode](#sdk-library-development-mode)
  * [Flash](#flash)
    + [J-Link](#j-link)
    + [ST-Link](#st-link)
  * [SDK Version](#sdk-version)
    + [Checkout](#checkout)
    + [Update](#update)
  * [Path Variables](#path-variables)
  * [Documentation](#documentation)

## Installation

### Prerequisites

* OS: macOS, Linux, Windows (WSL2 based Linux)
* Python3

### Install command

```
python3 -m pip install nola_tools
```

### Update command

```
python3 -m pip install nola_tools --upgrade
```

## Usage

### Login

For private users,
```
nola login={user name}:{token}
```

### Print information

```
nola info
```

### Build

```
nola build
```

If you want to change the board, specify the new board name like below:
```
nola build={new board name}
```

You can retrieve the available boards by using ```nola info```.

#### SDK Library Development Mode

For private users,

```
nola devmode={path to libnola source directory}
```

### Flash

```
nola flash={options...}
```
The options must be specified according to which debugger is used.

#### J-Link

To use J-Link as a flashing tool, setting ```jlink``` path variable is required.

For macOS, and Linux users,
```
nola path=jlink:{Absolute path to JLinkExe}
```

For Windows WSL2 users, the ```JLink.exe``` in the Windows region must be used.

```
nola path=jlink:/mnt/c/Program\\\ Files/SEGGER/JLink_V794/JLink.exe
```

The ```flash``` option must be ```jlink```.
```
nola flash=jlink
```

#### ST-Link

To use ST-Link as a flashing tool, setting ```stm32cube``` path variable is required.

For macOS, and Linux users,
```
nola path=stlink:{Absolute path to STM32_Programmer_CLI}
```

For Windows WSL2 users, the ```STM32_Programmer_CLI.exe``` in the Windows region must be used.
```
nola path=stm32cube:/mnt/c/Program\\\ Files/STMicroelectronics/STM32Cube/STM32CubeProgrammer/bin/STM32_Programmer_CLI.exe
```

If you want to use the SWD interface,
```
nola flash=stlink:swd
```

If you want to use the ST's internal system bootloader,
```
nola flash=stlink:/dev/ttyUSB0
```

```
nola flash=stlink:/dev/cu.usbmodem0000
```

```
nola flash=stlink:com3
```

### SDK Version


#### Update

You can update the SDK version like below:
```
nola update
```

#### Checkout

The current and available SDK version numbers can be retrieved by using ```nola info``` command.

You can change the SDK version number like below:
```
nola checkout={new version number}
```
You can check out the latest version by omitting the version number.
```
nola checkout
```

### Path Variables
In order to use commands such as ```flash```, external application paths must be specified first.

```
nola path={key}:{value}
```

You can also retrieve all specified paths like below:
```
nola path
```

### Documentation
You can open the SDK API book by simply typing below:
```
nola doc
```
