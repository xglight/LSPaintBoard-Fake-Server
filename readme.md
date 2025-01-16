# LSPaintBoard-Fake-Server

![](https://img.shields.io/badge/Python-3.10.11-blue)

LSPaintBoard 的伪服务器，用于模拟 LSPaintBoard 客户端与服务器的通信。

可用来测试脚本。

## 说明

LSPaintBoard-Fake-Server 并未实现 IP 链接数限制。

## 使用

下载 [LSPaintBoard-Fake-Server.exe](https://github.com/xglight/LSPaintBoard-Fake-Server/releases/latest)。

```bash
.\LSPaintBoard-Fake-Server.exe
```

可指定参数：

|    参数    |  类型  |  默认值   | 说明           |
| :--------: | :----: | :-------: | :------------- |
|    port    |  int   |   2380    | 端口号         |
|    host    | string | localhost | 主机名         |
| time_limit |  int   |   30000   | token 冷却时间 |

调用实例：

```bash
.\LSPaintBoard-Fake-Server.exe --port 2380 --host localhost --time_limit 30000
```

帮助：

```bash
.\LSPaintBoard-Fake-Server.exe --help
```

## 手动编译

```bash
git clone https://github.com/xglight/LSPaintBoard-Fake-Server.git
cd LSPaintBoard-Fake-Server
pip install -r requirements.txt
pyinstaller LSPaintBoard-Fake-Server.spec
```

