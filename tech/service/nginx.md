# 高性能Nginx

# Nginx初探

## Nginx的功能

- http基本服务
  - 静态文件服务,处理索引和自动索引
  - 打开并自行管理文件描述符缓存
  - 提供反向代理服务,并且可以使用缓存加速反向代理,同时完成简单负载均衡及容错
  - 提供远程FastCGI服务的缓存机制,加速访问,同时完成简单负载均衡及容错
  - 使用nginx的模块化特性,提供过滤器功能.包括gzip,ranges,chunked,XSLT,SSI,图片缩放等
  - 支持SSL
- http高级服务
  - 支持基于名字和ip的虚拟主机设置
  - 支持http/1.0中的keep-alive模式和pipelined模式连接
  - 支持重新加载配置,无需中断正在处理的请求
- 邮件代理服务

## Nginx常用功能

- HTTP代理和反向代理
- 负载均衡
  - 内置策略
    - 轮询 按照时间或者排列次序依次发送给后端节点
    - 加权轮询 在基本轮询基础加了权重,当节点性能不一样时会使用它
    - IP hash 根据ip来转发
  - 第三方策略
    - URL hash 根据URL来转发
    - fair 转给最近负载最小的节点(根据节点响应时间决定负载情况)
- 缓存(主要由proxy_cache和fastcgi_cache相关指令构成)

# 安装

- 快速停止:立即停止所有的处理请求`kill TERM|INT nginx.pid`后者`kill -9 | SIGKILL nginx.pid`
- 平滑停止:等待正在处理请求完成`kill QUIT nginx.pid`
- 平滑重启:`nginx -g HUP [-c 配置文件]`这里会检查配置文件,配置文件正确就重启
- TERM,INT 快速关闭
- QUIT 从容关闭
- HUP 平滑重启
- USR1 重新打开日志文件,切割日志文件时用处较大
- USR2 平滑升级
- WINCH 从容关闭工作进程

## 基础配置指令

### 配置文件结构`nginx.conf`

```json
{
  全局配置块;nginx的全局配置指令
  events{
  	events配置块;主要影响nginx服务器与用户的网络连接,这一部分对nginx的性能影响较大
  }
  http{
    http全局配置块
    server1{
    	server全局配置块
      location1{
    		location配置块
      }
      location2{
    		location配置块
      }
    }
    server2{
  		server全局配置块
    }
  }
}
```

## 全局配置块

- `user user [group]` 指定只能特定的用户才能启动nginx
- `worker_processes 数字|auto` 实现并发服务的关键所在
- `pid pid文件名`
- `error_log 日志文件名|stderr [debug|info|notice|warn|error|crit|alert|emerg]`进程运行时的日志
  - stderr表示输出日志到标准错误输出stderr
- `include 配置文件名`可以包含其他配置文件(可以在http,server,location中使用)

## events配置块

- `accept_mutex on|off`当只有一个连接时,为了防止多个进程被唤醒,争抢处理该链接,当开启accept_mutex时.进程接受连接进行序列化,从而避免唤醒多个进程,**默认 on**
- `multi_accept on|off`每个worker process都可以同时接受多个新到达的网络连接,但是需要通过multi_accept开启,**默认 off**
- `use 事件驱动模型` 常用选项`select|poll|kqueue|epoll|rtsig|/dev/poll|eventport`
- `worker_connections 数字`worker process同时开启的最大连接数,**不能超过操作系统支持的最大打开文件句柄数**,**默认 512**

## http全局配置块

- `include mime.types` 包含当前目录下的mime.types中的媒体类型
- `default_type mime-type` mime-type就是mime.type中定义的媒体类型,定义处理前端请求的MIME类型(还可以在server和location中使用)
- `access_log path[format[buffer=size]]`服务器应答前端请求的日志,与全局配置块error_log不同
  - path日志文件名
  - format自定义服务日志的格式字符串,使用`log_format指定格式的格式串名称`
  - size临时存放日志的内存缓存大小
  - 例如`access_log logs/access.log combined;`
- `access_log off`关闭请求日志
- `log_format 日志名 格式串;`与access_log关联紧密,格式串
  - 例如:`log_format logtest '$remote_addr - [$time_local] $request $status $body_bytes_sent  $http_referer $http_user_agent ;'`

- `sendfile on|file`配置允许通过sendfile()传输文件,(可以在http,server.location中使用)
- `sendfile_max_chunk size;`与sendfile配合使用,表示worker process每次调用sendfile()传输的数据量最大不能超过这个值,如果size=0表示无限制
- `keepalive_timeout timeout[header_timeout]` timeout服务对连接的保持时间,默认75s,(可以在http,server,location中使用)
  - header_time在应答报文头部`Keep-Alive`设置超时时间
  - 例如: `keeplive_timeout 120s 100s;`
- `keepalive_requests 数字`保持连接时,客户端允许在该连接上发起的请求最大次数,默认100(可以在http,server,location中使用)

## server全局配置块

### 监听网络`listen`有三种方式

- `listen address[:port] [default_server] [setfib=number] [backlog=number] [rcvbuf=size] [sndbuf=size] [deferred] [accept_filter=filter] [bind] [ssl]` 配置监听的IP
- `listen port [default_server] [setfib=number] [backlog=number] [rcvbuf=size] [sndbuf=size] [accept_filter=filter] [deferred] [bind] [ipv6only=on|off] [ssl]` 配置监听的端口
- `listen unix:path [default_server] [backlog=number] [rcvbuf=size] [sndbuf=size] [accept_filter=filter] [deferred] [bind] [ssl]` 配置监听的Unix Domain Socket

##### 参数说明:

- `address` IP地址,如果是IPV6要放在"[]" 
- `port` 端口号,如果只定会IP没有定义端口,那么默认80
- `path` socket文件路径
- `default_server` 标识符,将此虚拟机设置为address:port的默认主机
- `setfib=number`使用这个变量监听关联路由表,只对FeeBSD有效
- `backlog=number` 设置监听函数listen()最多允许多少网络连接同时处于挂起状态,默认511
- `recv_buf=size`设置监听socket接受缓冲区大小
- `snd_buf=size`设置监听socket发送缓冲区大小
- `deferred` 标识符,将accept()设置为Deferred模式
- `accept_fileter=filter`设置箭筒端口对请求的过滤,被过滤内容不能被接受和处理,只在FreeBSD和NetBSD下有效
- `bind`标识符,使用独立的bind()处理此address:port 一般情况下,对于端口相同而IP不同的多个链接,Nginx服务器将只是用一个监听命令,并使用bind()处理端口相同的所有链接
- `ssl` 标识符,设置回话链接使用SSL模式进行

```shell
listen 192.168.1.10:8000 ; # 监听具体的IP和端口
listen 192.168.1.10 ; # 监听IP上所有端口的链接
listen 8000; # 监听所有IP的具体端口的连接,类似于 *:8000
```



### 基于名称的虚拟主机配置

`server_name name ...;` 配置虚拟主机的域名,表示此虚拟机接受那些域名的请求

```shell
server_name www.example.com;
server_name *.example.com;
server_name api.example.com,api.v1.example.com;
server_name www.api.*;
server_name ~^www\d+\.example\.com$;#正则表达式
- ~ 字符串开始标志
- ^ 字符串开头
- \d数字
- + 多个
- . 任意字符
- \转义
- $ 字符串结尾
也可以使用正则捕获分组`server_name ~^www\.(.+)\.example\.com`,这样可以在下文中使用$1,$2等变量名来使用

```

### 基于IP的虚拟主机设置

linux支持IP别名的添加.基于IP的虚拟主机,即为Nginx服务器的每台虚拟主机配置一个不同的IP,因此需要网卡设置能够监听多个IP地址,使用ifconfig来为一个网卡添加多个IP别名

`ifconfig eth0:1 192.168.1.51 netmask 255.255.255.0 up`

`ifconfig eth0:2 192.168.1.52 netmask 255.255.255.0 up`

其他主机可以通过 192.168.1.51,192.168.1.52 Ping通

`server_name: 192.168.1.51`当客户端请求的是192.168.1.51时请求被当前虚拟主机接受,**注意格式与域名不同**

### location

`location  [=|~|~*|^~] uri ...;`

- `=` 严格匹配uri,如果匹配到就不再继续往下
- `~` uri包含正则,区分大小写
- `~*` uri包含正则,不区分大小写
- `^~` 禁止匹配到字符串后，再去检查正则表达式

先匹配字符串，在匹配正则表达式，即使已经匹配到了字符串，也会继续向下继续匹配正则表达式，如果匹配到正则表达式就使用正则表达式，如果没有正则表达式，就使用匹配到的字符串，除非匹配的字符串使用的是`^~`或者`=`定义的，

正则表达式是从上往下一个个匹配

一般把字符匹配写在最上面，因为他们优先匹配，正则放下面

#### root

指明请求接受到后,在哪里寻找资源 `root /var/www;`

#### 更改location的uri

`alias path` path为修改后的路径

```
location ~ ^/api/bioinfo/(.+)$ 
{
  alias /location/bioinfo/$1 ;
}
```

#### 网站默认首页

```
location ~ ^/data/(.+)/web/$ 
{
  index index.$1.html index.my1.html index.html;
}
```

### 设置错误页面

```
error_page 404 /404.html
location /404.html
{
  root /myserver/errorpages/ ;
}
error_page 500 http://www.example.com/500.html;

error_page 410 =301 /empty.gif;#将410转为301返回给客户端
```

### 基于IP配置访问权限(可以在http,server,location中使用)

`allow address|CIDR|all;`

- `address`表示ip地址,如果多个ip,那么需要多条allow

- `CIDR` `192.168.1.100/25`表示前面25位是网络部分,其余为主机部分

- `all` 允许所有客户端访问

`deny address|CIDR|all`和all一样

如果有多条deny和allow,那么从上往下匹配,只要匹配一条就不再继续往下

### 基于密码配置访问权限

使用的是HTTP Basic Authentication

`auth_basic string|off;`

- `string` 开启认证功能,并配置验证时的指示信息

- `off` 关闭认证

`auth_basic_user_file file;`file包含用户名和密码信息,结构如下

```shell
name1:password1
name2:password2
```

# Nginx的模块化

Nginx的核心是run-loop,异步事件驱动

Nginx的进程关系,主进程,工作进程

主进程和工作进称通过管道通信,工作进程之间也通过管道通信

# Nginx高级配置

## 针对IPv4的内核7个参数配置优化

### net.core.netdev_max_backlog 

表示每个网络接口接收数据包的速率比内核处理这些数据包的速率快时,允许发送到队列中数据包最大数目

nginx中NGX_LISTEN_BACKLOG默认是511 

这里修改为

net.core.netdev_max_backlog = 262144

### net.core.somaxconn

用于调节系统同时发起的TCP连接数,默认是128.如果客户端存在高并发请求的情况下,该值较小,可能导致链接超时或者重传问题

net.core.somaxconn = 262144

### net.ipv4.tcp_max_orphans

该参数用于设定系统中最多允许存在多少TCP套接字不被关联到任何一个用户文件句柄上,如果超过这个数字,没有被用户句柄关联的TCP套接字,将会被复位,主要用于防止DoS,

如果内存充足可以适当调高 net.ipv4.tcp_max_orphans = 262144

### net.ipv4.tcp_max_syn_backlog

该参数用于记录尚未收到客户端确认信息的连接请求的最大值.对于用于128MB的系统参数默认值是1024,

如果内存充足可以调高 net.ipv4.tcp_max_syn_backlog = 262144

### net.ipv4.tcp_timestamps 

该参数用于设置时间戳,可以避免序列号的卷绕,在1Gb/s的链路上,遇到以前用过的序列号概率很大,该值为0时,禁用对于TCP时间戳的支持.

对于Nginx应当关闭 net.ipv4.tcp_timestamps = 0

### net.ipv4.tcp_synack_retries

该参数用于设置内核放弃TCP连接之前向客户端发送SYN+ACK包的数量,就是3次握手过程.一般赋值为1

net.ipv4.tcp_synack_retries = 1

### net.ipv4.tcp_syn_retries

与上一个类似

net.ipv4.tcp_synack_retries = 1

将这些参数写入`/etc/sysctl.conf`执行`sysctl -p`使得参数生效

## 针对CPU优化Nginx

`worker_processes`和`worker_cpu_affinity`

一般CPU有几个核心就设置几个`worker_processes`,worker_cpu_affinity指明worker进程在哪一个核心上运行

如果是4核心CPU 4进程,那么`worker_cpu_affinity 0001 0010 0100 1000;`

如果是4核心CPU 8进程,那么`worker_cpu_affinity 0001 0010 0100 1000 0001 0010 0100 1000;`

如果是8核心CPU 8进程,那么`worker_cpu_affinity 00000001 00000010 00000100 00001000 00010000 00100000 01000000 10000000;`

0表示不适用这个核心,1表示使用这个核心

有多少个进行就要设置多少个 数字串,有几个CPU核心那么数字串中数字就有几个

## 与网络连接相关的配置

`keepalive_timeout 60s 50s`单位秒第二个50是响应给客户端的,告知客户端服务器保持连接的时长

`send_timeout 时间s` nginx与客户端建立连接后,等待客户端响应的时间,超过这个时间,连接就关闭

`client_header_buffer_size 4k;`客户端发起的请求头部数据可能很大,nginx需要更过的缓存区来处理请求头

`multi_accept on|off` 默认off,配置nginx是否尽可能多的接受客户端的网络连接请求

## 事件驱动模型相关配置

`use method` 使用的事件驱动模型

`worker_connections number` 每个工作进程允许同时连接的客户端数量,常见服务器日志和此有关

`worker_connections is not enough while accepting new connection`表示并发较大,需要调大此值

`worker_connnection are more than open file resource limit:1024` 改成打开的文件句柄数超过操作系统的限制了,此时需要调大操作系统限制,`echo '2390251' > /proc/sys/fs/file-max; sysctl -p`

`epoll _changes number`epoll 驱动模式下nginx服务器可以与内核之间传递事件的数量

# Gzip压缩(http,server,location)

 `gzip on|off`开启或者关闭gzip

`gzip_buffers number size`gzip压缩文件使用缓存空间大小,number表示申请多少个缓存空间,size表示每个缓存空间大小,size一般为4k或者8k number一般对应的是32 ,16

`gzip_com_level 0~9`压缩级别,9最大压缩率,最费时间

`gzip_disable regex_str` 使用正则来匹配客户端的User-Agent,匹配成功则该请求不适用gzip

`gzip_http_version 1.0|1.1` 针对客户端使用的http协议来决定使用启用gzip

`gzip_min_length number`对于大数据gzip压缩有效,但是小数据可能压缩后更大,这里的number数据会响应头的Content-Length对比,一般设置为1024即为1kB以上才压缩

`gzip_types mime-type`将那些MIME响应进行压缩

`gzip_vary on|off`是否在响应头添加`Accept-Encoding:gzip`头

`gunzip_static on|off|always `客户端请求的数据可能预先被压缩已.gz后缀保存在服务器上,开启该功能,nginx会查找请求数据是否存在.gz,如果有直接返回该.gz数据

`gunzip on|off` 当作为代理服务器时,后端服务器返回的数据可能已经被压缩了,但是客户端不能够解析压缩的数据,开启这个命令,会先将后端服务器数据解压缩,然后返回给客户端.

`gunzip _buffers number size`缓存空间

# Rewrite

有了rewrite重定向才够灵活

## Upstream

通过 upstream 可以定义一组后端服务器,用于负载均衡,反向代理等功能

server 定义

- `address` 服务器地址,可以是 `ip:port` 或者 `unix:`
- `weight=number` 轮询加权重
- `max_fails=number` 在一定时间内,该 server 请求失败次数超过此值时,该服务器变为无效**404不被任务是失败**
- `fail_timeout=time` 两个作用,一是执行 max_fails 的时间范围, 二是加入此服务器无效了,那么在此时间范围内,不会去检查该服务器是否生效了,默认时间10s
- `backup` 将该服务器标记为备用服务器,当正常的服务器处于无效或者繁忙状态,该服务器才会被启用
- `down` 将该机器标记为无效状态
- `ip_hash` 根据客户端 ip 来分发请求,不能喝 weight 联合使用
- `least_conn` 根据最近最少负载来分发请求
- `keepalive connections;` 

```shell
upstream name # name 是 upstrema 的名字,可以定义多个 upstream
{
  ip_hash;#使用的分发算法,根据客户端的 ip 来分发
  server address [parameters];#可以定义多个 server,如果请求在某个 server 中出现错误,那么会转发给下一个 server 处理
}
```

## Rewrite

## 地址重写和地址转发

地值转发:客户端发起的请求被转发后,地址栏的地址不变，依次地址转发只产生一次请求。地址重写:地址重写后,客户地址的地址会改变，一次地址重写，发生两次请求。

### if指令(server,location)

`if (condition){}` 

`if ($slow)` 如果 `$slow` 以0开头或者是空字符串，那么条件为 false，否则为true

`if ($request_method = POST)` `if ($request_method != POST)` 比较是否与字符串(不)相等，字符串不需要加引号

`if ($http_user_agent ~ MSIE)` 正则匹配字符串 `~*` `!~` `!~*` 加 `!` 表示不匹配。

`if (-f $request_filename)`请求的**文件**是否存在 ，`!-f`**文件或者目录**是否不存在。

- `-d` `!-d` 目录是否存在
- `-e` `!-e` 目录或者文件
- `-x` `!-x` 文件是否可执行

### break 指令(server，location，if)

break 指令后面的配置会被忽略

### return 指令(server，location，if)

直接向客户端返回响应状态码，在 return 之后的指令都是无效的

`return [ text ]` text响应体内容

`return code URL;` code 状态码

`return URL;` URL 返回给客户端的 URL 地址

### rewrite 指令(server，location)

通过正则表达式来改变 URI，可以同时存在一个或者多个，按照顺序依次对 URL 进行匹配和处理

`rewrite regex replacement [flag]`

- regex 是匹配 URL 的正则表达式，使用`()`标记要截取的内容

rewrite接收到的是` http://{doamin}{path}{?args}`中的 `path` 所以只能去匹配 path

比如客户端访问 `http://localhost:8080/index.html`改写`rewrite (.*) https://localhost:8080$1`

### set 设置变量

`set name value` value 中可以包含 nginx 全局变量,name 用`$`作为第一个字符,并且不能喝全局变量冲突

# Nginx 全局变量

# Nginx作为代理服务器

正向代理:内部客户端通过代理服务器访问外网的网站 

反向代理:外部客户端通过代理服务器访问内部 web 服务器

## 正向代理服务器配置(http,server,location)

### resolver

用于指定 DNS 服务器的 IP 地址

`resolver address [valid=time]`

- `address` DNS 服务器的 IP 地址,默认端口号53
- `time` 数据包在网络中的有效时间,如果这段时间内,数据包没有到达目的地,就被丢弃

### resolver_timeout

域名解析超时时间

`resolver_timeout time;`

## 反向代理

`proxy_pass URL` URL作为代理服务器的地值，可以是 upstream 或者单个 URL，URL 一般要跟着传输协议(HTTP，HTTPS 等)

```shell
proxy_pass http://www.example.com/uri;
proxy_pass http://unix:/tmp/backend.socket:/uri/;
```

代理一组服务器

```shell
upstream test
{
  server 192.168.1.1:80001/uri/ ;
  server 192.168.1.2:80001/uri/ ;
  server 192.168.1.3:80001/uri/ ;
}
proxy_pass http://test ;#如果该组服务器包含了 http 协议，就不需要加 http:// 
```

关于`uri`结尾，如果不想改变原有的请求 url 就不在服务器后面加路径

```shell
location /server 
{
  # 配置1 proxy_pass http://192.168.1.1 ; #代理到http://192.168.1.1/server
  # 配置2 proxy_pass http://192.168.1.1/ ; #代理到http://192.168.1.1/
}
```

### proxy_hide_header(http,server,location)

`proxy_hide_header field`隐藏请求头部，不发送给代理服务器

### proxy_pass_header(http,server,location)

`proxy_pass_header field` 

默认情况下 nginx 不会把来自代理服务器的头部Date,Server,X-Accel等返回给客户端，这个指令指明携带哪些头部

### proxy_pass_request_body(http,server,location)

`proxy_pass_request_body on|off `默认 on，是否把请求体数据发送给代理服务器

### proxy_pass_request_headers(http,server,location)

`proxy_pass_request_headers on|off` 默认 on，是否将客户端请求头发送给代理服务器

### proxy_set_header

`proxy_set_header field value` 设置或者修改请求头，并发送给代理服务器

### proxy_set_body

`proxy_set_body value` 设置或者修改请求体，并发送给代理服务器

### proxy_connect_timeout

`proxy_connect_timeout time` 配置 nginx 与代理服务器尝试建立连接的超时时间

### proxy_read_timeout

`proxy_read_timeout time` 配置 nginx 向代理服务器发出 read 请求后，等待响应的超时时间

### proxy_send_timeout

`proxy_send_timeout time` 配置 nginx 向代理服务器发出 write 请求后，等待响应的超时时间

### proxy_http_version

`proxy_http_version 1.0|1.1`

### proxy_method

`proxy_method POST|GET` 配置 nginx 向代理服务器发起请求的方法，如果设置了这个，**那么客户端的请求方法将失效**

### proxy_ingore_client_abort

`proxy_ingore_client_abort on|off` 默认 off，当客户端中断网络连接时，nginx 是否中断与代理服务器的连接

### proxy_ignore_headers

`proxy_ignore_headers field...` nginx 收到代理服务器的响应后，将不会处理被忽略的头部

### proxy_intercept_errors

`proxy_intercept_errors on|off` 开启时，如果代理服务器返回的状态码大于等于400，那么 nginx 会使用自定义的错误处理页面，如果为 off，那么 nginx 会把代理服务器的状态返回给客户端

### proxy_next_upstream

`proxy_next_upstream status...`当代理一组服务器时，可以设置当请求状态满足一下条件时，将请求交给组内下一个服务器处理：

- error 在建立连接、向代理服务器发送请求后者读取响应头时服务器发生错误
- timeout 在建立连接、向代理服务器发送请求后者读取响应头时服务器发生连接超时
- invalid_header 代理服务器返回的响应头为空或者无效
- http_500|http_502|http_503|http_504|http_404，当服务器返回以下状态码时
- off，无法将请求发送给代理服务器

### proxy_ssl_session_reuse

`proxy_ssl_session_reuse on|off` 默认开启，表示是否使用 https 连接代理服务器



# Nginx 模块

核心模块、标准 http 模块、可选 http 模块、邮件模块、第三方模块。

## 主模块指令(配置文件最顶部)

## daemon

`daemon off|on`  默认 on , 可以在开发调试的时候使用 关闭守护进程,不要在生产中使用

## error_log 

错误日志存放的位置,以及日志级别

## log_not_found

`log_not_found on|off`默认 on , 可以禁用或启用404日志,当 NGINX找不到资源时,会记录404日志

```shell
location = /rebot.txt
{
  log_not_found off ;
}
```

## include

`include file`file 可以带匹配符,将配置文件包含进来

## pid

`pid file` 进程 pid 保存到那个文件中

## timer_resolution

`timer_resolution time` 如果想要记录毫秒级的准确时间,用此参数,他可以减少 `gettimeofday`函数获取当前时间的系统调用次数,例如:`timer_resolution 100ms`

## user

`user user group`指定运行 nginx 的用户和组

## worker_cpu_affinity[针对CPU优化Nginx]

## worker_processes

工作进程的数量,一般为 CPU 核心数

## worker_rlimit_core

指定每个 nginx 进程的最大 core 文件大小

## worker_rlimit_nofile

`worker_rlimit_nofile number` 指定 nginx 进程可以打开的最大文件描述符数量

## working_directory

`working_directory path` 指定 nginx 的工作目录,**只能使用绝对路径** 

 # 主模块变量

- `$nginx_version` nginx版本号
- `$pid` 进程号
- `$realpath_root` root 目录的绝对路径

## 事件模块指令(event 指令)

## accept_mutex

`accept_mutex on|off` 默认 on , Nginx 使用连接互斥锁进行顺序的 accept 系统调用

##accept_mutex_delay

`accept_mutex_delay time` 默认 500ms  如果一个进程没有互斥锁，那么他将在最少 time 毫秒延迟后再次尝试获得互斥锁

## use

`use epoll|kqueue…` 使用的事件模型

## worker_connections

`worker_connections number` 每个工作进程能投处理的连接数，最大不能超过操作系统允许打开的文件描述符数

# HTTP模块(http:h，server:s，location:l,a:h,s,l)

## client_body_buffer_size

`client_body_buffer_size size` 默认 8k或者16k，指定客户端请求内容的缓冲区大小，如果客户端请求内容大于缓冲区，整个请求内容或部分内容将被写入临时文件，这里需要和`client_body_temp_path`联合使用

## client_body_temp_path

`client_body_temp_path dirname ` 指定请求内容临时文件目录

## client_body_timeout

`client_body_timeout time` 默认60 设置读取客户端请求内容的超时时间，如果超过改时间 nginx 返回408状态码

## client_header_buffer_size(hs)

`client_header_buffer_size size` 默认1k，设置客户端请求头缓冲区大小，如果 cookie 较大可以调大此值

## client_header_timeout(hs)

`client_header_timeout time` 默认60，读取客户端请求头的超时时间和`client_body_timeout`一样

## client_max_body_size

`client_max_body_size size` 默认1m，客户端发起的内容最大值，超过此值就返回413

## default_type

默认的 MIME-type，如果 nginx 不能识别返回的文件媒体类型，就使用这个默认类型，返回给客户端

## directio

`directio [size|off]` 默认 off，是否使用 DMA 直接读取文件，如果文件很大，使用 DMA 效率会高一些，例如:`directio 4m;`

## error_page

`error_page code... URI`

例如:`error_page 401 403 /denied.html` ; `error_page 401 =200 /denied.html` 状态码变为200

`error_page 500 http://example.com/denied.html` 

## large_client_header_buffers(hs)

`large_client_header_buffers size`默认4k 或者8k，设置客户端请求头缓冲区大小，如果超过该值 nginx 返回400或者414

## limit_except(l)

`limit_except methods {...}` 显示 http 方法访问 location 中的内容

```shell
limit_except GET {
  allow 192.168.1.0/32 ;
  deny all;
}
```

## limit_rate

`limite_rate [size|no]` 默认 no，限制数据发送速率，单位`字节数/s` 例如:`limite_rate 100k;`，只对单个连接有效

## limit_rate_after

`limit_rate_after size`超过一定数据量之后限速，配合`limit_rate`使用

## sendfile

`sendfile on|off`默认 off，sendfile 可以提高效率

## expires

- `epoch` 指定 Expires 头为`1 January,1970,00:00:01 GMT`
- `max` 指定Expires的值为`31 December 2037 23:59:59 GMT`
- `-1` 指定 Expires的值为服务器时间`-1s`，就是永远过期
- 负数 指定 Expires 的值为`Cache-Control:no-cache`，就是不缓存
- 证书或者0，就是 `Cache-Control: max-age=指定的值`
- `off` 表示不修改 `Expires` 和 `Cache-Control` 值

## add_header

`add_header name value`设置响应头

## proxy_pass



## ssl_certificate 

## ssl_cerrificate_key

```shell
server {
  listen 443 ssl;
  ssl_certificate /path/to/cert.pem;
  ssl_certificate_key /path/to/cert.key
}
```

