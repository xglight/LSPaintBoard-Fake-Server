# LSPaintBoard-Fake-Server

![](https://img.shields.io/badge/Python-3.10.11-blue)

LSPaintBoard 的伪服务器，用于模拟 LSPaintBoard 客户端与服务器的通信。

可用来测试脚本。

## 说明

1. LSPaintBoard-Fake-Server 并未实现 IP 链接数限制。
2. 全部使用 http 协议，不支持 https。

## 使用

下载 [LSPaintBoard-Fake-Server.exe](https://github.com/xglight/LSPaintBoard-Fake-Server/releases/latest)。

```bash
.\LSPaintBoard-Fake-Server.exe
```

帮助：
```bash
.\LSPaintBoard-Fake-Server.exe --help
```

## 参数

可以在 `config.json` 文件中编辑，也可以使用命令行传参启动。

### server

|    参数    | 类型  |  默认值   |      说明      |
| :--------: | :---: | :-------: | :------------: |
|    port    |  int  |   2380    |   服务器端口   |
|    host    |  str  | localhost |   服务器地址   |
| time_limit |  int  |     0     | token 冷却时间 |

### api
| 参数  | 类型  |  默认值   |     说明      |
| :---: | :---: | :-------: | :-----------: |
| host  |  str  | localhost | API服务器地址 |
| port  |  int  |   4796    | API服务器端口 |

## 手动编译

```bash
git clone https://github.com/xglight/LSPaintBoard-Fake-Server.git
cd LSPaintBoard-Fake-Server
pip install -r requirements.txt
pyinstaller LSPaintBoard-Fake-Server.spec
```

