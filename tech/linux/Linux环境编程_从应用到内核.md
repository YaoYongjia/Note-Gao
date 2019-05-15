# Linux环境编程:从应用到内核

# 基础知识

# 文件 I/O

## Linux 中的文件

Linux 中一切皆文件,物理文件、设备、管道、内存。广义就是 Linux 管理的所有对象，这些文件利用 VFS 机制，以文件系统的形式挂在在 Linux 内核中，对外提供一致的文件操作接口。

**文件描述符**是一个非负整数，本质是一个句柄，句柄对用户是透明的。用户空间利用文件描述符与内核进行交互。内核利用文件描述符管理真正的数据。

每个进程都维护一个文件表，用于维护该进程代开文件的信息，例如：打开个数，每个打开文件偏移量等。

### 内核文件的实现

```c
/*
 * Open file table structure
 */
struct files_struct {
  /*
   * read mostly part
   */
	atomic_t count;
	bool resize_in_progress;
	wait_queue_head_t resize_wait;

	struct fdtable __rcu *fdt;
	struct fdtable fdtab;
  /*
   * written part on a separate cache line in SMP
   */
	spinlock_t file_lock ____cacheline_aligned_in_smp;
	unsigned int next_fd;
	unsigned long close_on_exec_init[1];
	unsigned long open_fds_init[1];
	unsigned long full_fds_bits_init[1];
	struct file __rcu * fd_array[NR_OPEN_DEFAULT];
};
```

init 是 linux 第一个进程,他的文件表是
```c
struct files_struct init_files = {
	.count		= ATOMIC_INIT(1),
	.fdt		= &init_files.fdtab,
	.fdtab		= {
		.max_fds	= NR_OPEN_DEFAULT,
		.fd		= &init_files.fd_array[0],
		.close_on_exec	= init_files.close_on_exec_init,
		.open_fds	= init_files.open_fds_init,
		.full_fds_bits	= init_files.full_fds_bits_init,
	},
	.file_lock	= __SPIN_LOCK_UNLOCKED(init_files.file_lock),
};
```

## 打开文件

`int open(const char *pathname, int flags, mode_t mode);`

open接收可变参数,glibc声明是 `extern int open(__const char *__file, int __oflag, ...) __nonnull((1));`

- pathname: 要打开的文件路径
- flags: O_RDONLY==0、O_WRONLY==1和O_RDWR==2
- mode: 只在创建文件事需要,用于指定所创建文件的权限为(收到 umask 影响)

### 更多选项

- O_APPEND: 每次写操作都会追加到文件末尾
- O_ASYNC: 使用异步 I/O 模式
- O_CLOEXEC: 在打开文件的时候，就为文描述符设置 FD_CLOEXEC 标志，这是一个新的选项，用于解决在多线程下fork与用fcntl设置FD_CLOEXEC的竞争问题。在多线程下，可能会在fcntl调用前，就已经fork出子进程了，从而导致该文件句柄暴露给子进 程。
- O_CREAT: 当文件不存在时，就创建文件
- O_DIRECT:对该文件进行直接I/O，不使用VFS Cache。
- O_DIRECTORY: 要求打开的路径必须是目录。
- O_EXCL:该标志用于确保是此次调用创建的文件，需要与O_CREAT同时使用;当文件已经存在 时，open函数会返回失败
- O_LARGEFILE:表明文件为大文件
- O_NOATIME:读取文件时，不更新文件最后的访问时间。
- O_NONBLOCK、O_NDELAY:将该文件描述符设置为非阻塞的(默认都是阻塞的)
- O_SYNC:设置为I/O同步模式，每次进行写操作时都会将数据同步到磁盘，然后write才能返回。
- O_TRUNC:在打开文件的时候，将文件长度截断为0，需要与O_RDWR或O_WRONLY同时使用。

> 不一定所有文件系统都支持上面选项

### open 源码跟踪

open->do_sys_open

```c
long do_sys_open(int dfd, const char __user *filename, int flags, umode_t mode)
{
	struct open_flags op;
    /* flags为用户层传递的参数，内核会对flags进行合法性检查，
    并根据mode生成新的flags值赋给fd */
	int fd = build_open_flags(flags, mode, &op);
	struct filename *tmp;

	if (fd)
		return fd;//没有出错返回文件句柄


	tmp = getname(filename);
	if (IS_ERR(tmp))
		return PTR_ERR(tmp);
    
	fd = get_unused_fd_flags(flags);
	if (fd >= 0) {
        // 申请新的文件管理结构
		struct file *f = do_filp_open(dfd, tmp, &op);
		if (IS_ERR(f)) {
			put_unused_fd(fd);
			fd = PTR_ERR(f);
		} else {
            // 将文件描述符fd与文件管理结构file对应起来，即安装
			fsnotify_open(f);
			fd_install(fd, f);
		}
	}
	putname(tmp);
	return fd;
}
```
do_sys_open可以看出，打开文件时，内核主要消耗：文件描述符与内核管理文件结构 file

### 如何选择文件描述符

根据POSIX标准，当获取一个新的文件描述符时，要返回最低的未使用的文件描述符.

`do_sys_open->get_unused_fd_flags->alloc_fd(0，(flags))`

```C
static int alloc_fd(unsigned start, unsigned flags)
{
	return __alloc_fd(current->files, start, rlimit(RLIMIT_NOFILE), flags);
}
/*
 * allocate a file descriptor, mark it busy.
 */
int __alloc_fd(struct files_struct *files,
	       unsigned start, unsigned end, unsigned flags)
{
	unsigned int fd;
	int error;
	struct fdtable *fdt;
    // files为进程的文件表，下面需要更改文件表，所以需要先锁文件表
	spin_lock(&files->file_lock);
repeat:
    // 得到文件描述符表
	fdt = files_fdtable(files);
	fd = start;
    // 从start开始，查找未用的文件描述符。在打开文件时
    // files->next_fd为上一次成功找到的fd的下一个描述符。
    // 使用next_fd，可以快速找到未用的文件描述符;
	if (fd < files->next_fd)
		fd = files->next_fd;

    // 当小于当前文件表支持的最大文件描述符个数时，利用位图找到未用的文件描述符。
    // 如果大于max_fds怎么办呢?如果大于当前支持的最大文件描述符，那它肯定是未用的，就不需要用位图来确认了。
	if (fd < fdt->max_fds)
		fd = find_next_fd(fdt, fd);

	/*
	 * N.B. For clone tasks sharing a files structure, this test
	 * will limit the total number of files that can be opened.
	 */
	error = -EMFILE;
	if (fd >= end)
		goto out;
    // expand_files用于在必要时扩展文件表。
    // 何时是必要的时候呢?比如当前文件描述符已经超过了当前文件表支持的最大值的时候。
	error = expand_files(files, fd);
	if (error < 0)
		goto out;

	/*
	 * If we needed to expand the fs array we
	 * might have blocked - try again.
	 */
	if (error)
		goto repeat;

	if (start <= files->next_fd)
		files->next_fd = fd + 1;

	__set_open_fd(fd, fdt);
	if (flags & O_CLOEXEC)
		__set_close_on_exec(fd, fdt);
	else
		__clear_close_on_exec(fd, fdt);
	error = fd;
#if 1
	/* Sanity check */
	if (rcu_access_pointer(fdt->fd[fd]) != NULL) {
		printk(KERN_WARNING "alloc_fd: slot %d not NULL!\n", fd);
		rcu_assign_pointer(fdt->fd[fd], NULL);
	}
#endif

out:
	spin_unlock(&files->file_lock);
	return error;
}
```

### 文件描述符fd 与文件管理结构 file

内核使用 fd_install 将文件 file 与 fd 组合起来

```c
void fd_install(unsigned int fd, struct file *file)
{
	__fd_install(current->files, fd, file);
}
void __fd_install(struct files_struct *files, unsigned int fd,
		struct file *file)
{
	struct fdtable *fdt;

	rcu_read_lock_sched();

	if (unlikely(files->resize_in_progress)) {
		rcu_read_unlock_sched();
		spin_lock(&files->file_lock);
		fdt = files_fdtable(files);
		BUG_ON(fdt->fd[fd] != NULL);
		rcu_assign_pointer(fdt->fd[fd], file);
		spin_unlock(&files->file_lock);
		return;
	}
	/* coupled with smp_wmb() in expand_fdtable() */
	smp_rmb();
	fdt = rcu_dereference_sched(files->fdt);
	BUG_ON(fdt->fd[fd] != NULL);
	rcu_assign_pointer(fdt->fd[fd], file);
	rcu_read_unlock_sched();
}
```

当用户使用 fd 与内核交互时,内核可以使用 fd 从 fdt->fd[fd]中得到内部管理文件的结构 struct_file

## create

create就是`open(pathname，O_WRONLY|O_CREAT|O_TRUNC，mode)`

## 关闭文件

close 用于关闭文件描述符.文件描述符可以普通文件、设备、socket等。在关闭时，VFS 会根据不同的文件类型，执行不同的操作。

### close 源码跟踪

```c
/*
 * The same warnings as for __alloc_fd()/__fd_install() apply here...
 */
int __close_fd(struct files_struct *files, unsigned fd)
{
    //files当前进程的文件表

	struct file *file;
	struct fdtable *fdt;

	spin_lock(&files->file_lock);
    // 通过文件表，取得文件描述符表
	fdt = files_fdtable(files);
    //参数fd大于文件描述符表记录的最大描述符，那么它一定是非法的描述符
	if (fd >= fdt->max_fds)
		goto out_unlock;
    //利用fd作为索引，得到file结构指针
	file = fdt->fd[fd];
    // 检查filp是否为NULL。正常情况下，filp一定不为NULL。
	if (!file)
		goto out_unlock;
    // 清除fd在close_on_exec位图中的位
	rcu_assign_pointer(fdt->fd[fd], NULL);
    // 释放该fd，或者说将其置为unused。
	__put_unused_fd(files, fd);
	spin_unlock(&files->file_lock);
    // 关闭file结构
	return filp_close(file, files);

out_unlock:
	spin_unlock(&files->file_lock);
	return -EBADF;
}

static void __put_unused_fd(struct files_struct *files, unsigned int fd)
{
	struct fdtable *fdt = files_fdtable(files);
	__clear_open_fd(fd, fdt);
	if (fd < files->next_fd)
		files->next_fd = fd;
}
```
Linux 选择文件描述符是从小到大的顺序进行寻找的,文件表中 next_fd 用于记录下一次开始寻找的起点,当有空闲描述符时,即可分配.
当某个文件描述符关闭时,如果其小鱼 next_fd, 则 next_fd 就重置为这个描述符,这样下一次就会立即重用这个描述符。
**linux 永远会选择最小的可用的文件描述符**

最终使用的时文件系统的 release 函数,从而实现针对不同的文件类型来执行不同的关闭操作


## 自定义 files_operations

linux中不同文件类型使用的操作函数定义在files_operations中,例如 socket 文件操作函数:

```c
static const struct file_operations socket_file_ops = {
	.owner =	THIS_MODULE,
	.llseek =	no_llseek,
	.read_iter =	sock_read_iter,
	.write_iter =	sock_write_iter,
	.poll =		sock_poll,
	.unlocked_ioctl = sock_ioctl,
#ifdef CONFIG_COMPAT
	.compat_ioctl = compat_sock_ioctl,
#endif
	.mmap =		sock_mmap,
	.release =	sock_close,
	.fasync =	sock_fasync,
	.sendpage =	sock_sendpage,
	.splice_write = generic_splice_sendpage,
	.splice_read =	sock_splice_read,
};
```

不同文件类型利用 `**_alloc_file`来申请文件描述符及文件管理结构 file 结构,他们最终都会调用alloc_file来申请文件管理结构 file,例如:

```c
struct file *sock_alloc_file(struct socket *sock, int flags, const char *dname)
{
	struct qstr name = { .name = "" };
	struct path path;
	struct file *file;

	if (dname) {
		name.name = dname;
		name.len = strlen(name.name);
	} else if (sock->sk) {
		name.name = sock->sk->sk_prot_creator->name;
		name.len = strlen(name.name);
	}
	path.dentry = d_alloc_pseudo(sock_mnt->mnt_sb, &name);
	if (unlikely(!path.dentry)) {
		sock_release(sock);
		return ERR_PTR(-ENOMEM);
	}
	path.mnt = mntget(sock_mnt);

	d_instantiate(path.dentry, SOCK_INODE(sock));

    // 这里把socket_file_ops赋值给了file->f_op 从而实现了 VFS 中可以调用 socket 文件系统自定义的操作
	file = alloc_file(&path, FMODE_READ | FMODE_WRITE,
		  &socket_file_ops);
	if (IS_ERR(file)) {
		/* drop dentry, keep inode for a bit */
		ihold(d_inode(path.dentry));
		path_put(&path);
		/* ... and now kill it properly */
		sock_release(sock);
		return file;
	}

	sock->file = file;
	file->f_flags = O_RDWR | (flags & O_NONBLOCK);
	file->private_data = sock;
	return file;
}
```

alloc_file

```c
struct file *alloc_file(const struct path *path, fmode_t mode,
		const struct file_operations *fop)
{
	struct file *file;

	file = get_empty_filp();
	if (IS_ERR(file))
		return file;

	file->f_path = *path;
	file->f_inode = path->dentry->d_inode;
	file->f_mapping = path->dentry->d_inode->i_mapping;
	file->f_wb_err = filemap_sample_wb_err(file->f_mapping);
	if ((mode & FMODE_READ) &&
	     likely(fop->read || fop->read_iter))
		mode |= FMODE_CAN_READ;
	if ((mode & FMODE_WRITE) &&
	     likely(fop->write || fop->write_iter))
		mode |= FMODE_CAN_WRITE;
	file->f_mode = mode;
	file->f_op = fop;
	if ((mode & (FMODE_READ | FMODE_WRITE)) == FMODE_READ)
		i_readcount_inc(path->dentry->d_inode);
	return file;
}
```

### 遗忘 close 造成的问题

- 文件描述符始终没有释放
- 文件管理的内存结构没有释放

当进程退出时, linux ,会关闭进程的文件释放内存,当进程不死,这些内存就一直在那边.

当再次申请文件描述符时,就会扩展当前文件表,如果打开超过了系统限制就会发生**Too many open files**错误

### 如何找到文件资源泄露

`lsof -p 进程号`查看进程打开了哪些文件

## 文件偏移

文件读写都是从当前位置开始的,读写结束后更新偏移量

### lseek 

`off_t lseek(int fd, off_t offset, in t whence);`执行成功后返回新的文件偏移量

- whence: 设置偏移量的参考位置:SEEK_SET文件的起始位置、SEEK_CUR文件的当前位置和SEEK_END文件末尾
- offset: 正负数都可以

> 新增值: SEEK_DATA 和 SEEK_HOLE 用于文件中的数据和空洞

### 小心 lseek 的返回值

lseek 执行错误时返回值回事-1,并且 errno 被设置为对应的值，如果返回值为-1，但是 errno 是0表示没有出错，因为有的文件是可以返回负数位置的

## 读取文件

`ssize_t read(int fd, void *buf, size_t count)`

从fd 中读取 count 个字节到 buf ,中，并且返回成功读取的字节数，同时将偏移量更新到相同的字节数,返回0表示已经到了文件末尾，read 可能读取到比 count 小的字节数。

如果 read 返回-1，那么要比较 errno 的值，如果是EAGAIN、 EWOULDBLOCK或EINTR，那么不能视为错误，因为EAGAIN、 EWOULDBLOCK是由于当前 fd 为非阻塞且没有可读数据时返回的,后者是由于 read 信号被中断所造成的。

### 部分读取

通常 fd 中数据小于 count 时,会把数据直接返回,但是有些 fd 类型不是这么玩的,

socket 文件在读操作时,如果 fd 中没有 count 数量的数据那么可能阻塞,而不是直接返回

read 操作需要根据接口说明来小心处理;

## 写入文件

`ssize_t write(int fd,const void *buf,size_t count)`

尝试从 buf 中取出 count 字节数数据写入到 fd 中,但是 count 有可能大于 buf 用于的数据

> read 和 write 都会调用 vfs_read 或 vfs_write

### 追加写的实现

## 文件的原子读写

O_APPEND 可是实现向文件末尾追加数据, Linux 还提供 pread 和 pwrite 从指定偏移量位置读取或写入数据,他们不会更改当前文件偏移量

## 文件描述符复制

```c
int dup(int oldfd);//会使用一个最小的未使用文件描述符作为复制后的文件描述符
int dup2(int oldfd, int newfd);// 如果 newfd 已经打开,那么闲关闭 newfd, 然后复制 oldfd
int dup3(int oldfd, int newfd, int flags);//flag 仅支持O_CLOEXEC,可在 newfd 上设置O_CLOEXEC标志,避免将文件内容暴露给子进程
```

## 文件数据的同步

为了提高性能,操作系统会对文件的 I/O 操作进行缓存处理,对于读操作,如果要读取的内容已经在文件缓存中,就直接读取文件缓存,对于写操作,会先将修改提交到文件缓存中,在合适的时候或者过一段时间后,操作系统才会将改动提交到磁盘上.

linux 提供3个接口:
- void sync(void); 是阻塞调用
- int fsync(int fd); 只同步指定的 fd, 并且直到完成才返回,不仅同步数据,还同步被修改过的文件元数据
- int fdatasync(int fd);只同步文件的实际数据内容,和会影响后面数据操作的元数据

同步函数保存在 file_operations中.

在不需要同步所有元数据时fdatasync性能更好

## 文件元数据

例如:访问权限、上次访问 的时间戳、所有者、所有组、文件大小等信息

### 获取元数据

- int stat(const char *path, struct stat *buf);指定文件路径的信息
- int fstat(int fd, struct stat *buf);文件描述的属性
- int lstat(const char *path, struct stat *buf);链接文件的自身属性

### 内核如何维护文件的元数据

`vfs_stat->vfs_fstatat->vfs_getattr`

所有的元数据都保存在 inode 中,文件分为两部分 inode 和文件数据.

### 权限位解析

通常是 rwx,还有三个不常见的标志位

#### SUID 权限位

当文件设置 SUID 权限位时,任何人执行该文件,都会拥有该文件的所有者权限。passwd 命令正是利用这个特性，来允许普通用户修改自己的密码，因为只有 root 用户才有修改密码文件的权限，当普通用户执行命令时，就具有了 root 权限，从而可以修改自己的密码

`int inode_change_ok(const struct inode *inode, struct iattr *attr)`判断进程是否拥有权限修改 inode 的属性即文件属性

#### SGID 权限位

与 SUID 类似,即组权限

#### Stricky 位

只有在目录上该位才有意义.当目录拥有该权限时,效果是所有用户都拥有写权限和执行权限,该目录下的文件也只能被 root 或文件所有者删除

## 文件截断

### truncate 与 ftruncate

- int truncate(const char *path, off_t length) 截断指定路径的文件
- int ftruncate(int fd, off_t length) 截断指定的 fd

文件截断通常是减小文件大小，但也可以扩充文件大小，扩充内容填充为0

### 为什么需要文件截断

如果文件中有内容,但是不想要就得内容,那么久需要使用截断,直接把问价截断 length 设置为0

# 标准 I/O 库

## stdin、stdout、stderr

当 linux 新建一个进程时，会自动创建3个文件描述符，0，1，2分别对应标准输入、标准输出、错误输出。
stdin、stdout、stderr是指针分别指向0，1，2。stdin 不可读。stdout 不可写。stderr 不可读写且没有缓存。

## I/O缓存引出的趣题

C 库的 I/O 接口对文件 I/O 进行了封装,为了提高性能,引入了缓存机制:全缓存、行缓存、无缓存。

全缓存一般用于访问真正的磁盘文件，C 库为文件访问申请一块内存，只有当文件内容将缓存填满或执行 flush 函数时，C 库才会将缓存内容写入内核中。

行缓存一般用于访问终端，当遇到一个换行符时，就引发真正的 IO 操作，行缓存是有固定大小的，就算没有遇到换行符，一旦缓存满了就会引发 IO 操作。

C 库立功了接口，用于修改默认的缓存行为：
```
#include <stdio.h>
void setbuf(FILE *stream,char *buf);
void setbuffer(FILE *stream, char *buf, size_t size);
void setlinebuf(FILE *stream);
int setvbuf(FILE *stream, char *buf, int mode, size_t size);
```

标准输出的行缓存例子:
```c
#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
int main(){
    printf("Hello ");
    if (0==fork()){
        printf("child \n");
        return 0;
    }
    printf("parent\n");
    return 0;
}
```
输出为
```
Hello parent 
Hello child
```
因为标准输出是行缓存,所以没有遇到换行时是不会输出的。fork 时候“Hello ”缓存也被复制到了子进程中，

如果父进程`printf("Hello \n");`那么就会输出:
```
Hello
parent
child
```
这里因为父进程行标准输出被清空了,所以子进程的标准输出父之过来是空的

## fopen 与 open

fopen 用于打开文件,但是最终是调用 open 函数。fopen 标志位对应 open 标志位：
- r-->O_RDONLY 只读方式打开文件
- r+-->O_RDWR 以读写方式打开文件
- w--> O_WRONLY|O_CREAT|O_TRUNC 以写方式打开文件,当文件存在时,大小截断为0,文件不存在就创建文件
- w+-->O_RDWR|O_CREAT|O_TRUNC 以读写方式打开文件,当文件存在就截断为0,不存在就创建文件
- a-->O_WRONLY|O_APPEND|O_CREAT 以追加方式打开文件,当文件不存在时,创建文件
- a+-->O_RDWR|O_APPEND|O_CREAT 以追加读写的方式打开文件,当文件不存在时,创建文件
- c-->无对应标志位 该文件流在 IO 操作时不能被取消
- e-->O_CLOEXEC 当进程执行 exec 时,该文件流会自动关闭
- x-->O_EXCL 创建文件时,如果文件已经存在, fopen 则返回失败而不是打开文件
- b-->无对应标志位 表示打开的文件时二进制流而不是文本流,该标志目前在 Linux 中时无用的


## fdopen 与 fileno

`FILE *fdopen(int fd, const char *mode);`

`int fileno(FILE *stream)`

linux提供了文件描述符, C 库提供了文件流,有时候需要在两种之间进行切换

fdopen 用于从文件描述符 fd 生成一个文件流, fileno 用于从文件流 FILE 得到对应的文件描述符

fdopen 实际是创建一个新的文件流 FILE, 并建立 FILE 与描述符的对应关系, 可以从FILE的`_fileno`得到 fd

无论是fdopen 还是 fileno 都要使用 fclose 来关闭文件,而不是用 close, 因为只有采用次方式才会释放 FILE 占用的内存


# 进程环境

## exit

当进程正常退出时,会调用 C 库的 exit 函数。当进程崩溃或者 kill 掉时，不会调用 exit，只会执行内核的进程退出操作。

exit函数主要用来执行所有注册的退出函数

## atexit

atexit 用于注册进程正常退出时的回调函数，如果注册了多个回调函数，那么使用 先进后出顺序执行。

```c
#include <stdlib.h>
#include <stdio.h>
static void callback1(void) {
    printf("callback1\n"); 
}
static void callback2(void) {
    printf("callback2\n"); 
}
static void callback3(void) {
    printf("callback3\n"); 
}
int main(void) {
    atexit(callback1); 
    atexit(callback2); 
    atexit(callback3); 
    printf("main exit\n");
    return 0;
}
// main exit
// callback3
// callback2
// callback1
```

atexit只有在程序正常退出时才会被调用,就是使用 exit 退出,或者 main 的 return 后

## 环境变量

进程启动时会从 shell 环境继承当前的环境变量,例如: PATH,HOME,TZ 等.可以使用`int putenv(char *string)`来增加,修改或删除当前进程的环境变量

string 格式是`名字=值`,如果不存在,则创建,存在则修改

putenv 参数必须要使用长期存在的内存,所以必须使用全局变量,常量或动态内存。

**最好使用 setenv 来设置环境变量**：`int setenv(const char *name,const char *value,int overwrite);`

## 使用动态库

平时编程时除了 C 库,还会用到大量的库文件,其中绝大部分是以动态库的方式来提供服务的

静态库在链接节点会被直接链接进最终的二进制文件中,因此可以不依赖于库文件

动态链接问价不会被链接到文件中,但是运行时需要加载动态库

### 编译和使用动态库

```c
#include <stdlib.h> 
#include <stdio.h>
void dynamic_lib_call(void) {
    printf("dynamic lib call\n"); 
}
```
`gcc -Wall -shared 4_5_2_dlib.c -o libdlib.so`
```c
#include <stdlib.h>
#include <stdio.h>
extern void dynamic_lib_call(void); 
int main(void)
{
    dynamic_lib_call();
    return 0; 
}
```

`gcc -Wall 4_5_2_main.c -o test_dlib -L ./-ldlib`

-L 指示 gcc在哪个目录中查找以来的库文件

但是上面编译后会执行会出错,因为动态库, 默认是到`/lib` 或者`/usr/lib`;可以通过修改`/etc/ld.so.conf`配置文件或者环境变量 `LD_LIBRARY_PATH` 指示额外的动态库路径

C 库还提供了 `dlopen`接口来支持手工加载动态库的功能:
```c
#include <stdlib.h> 
#include <stdio.h> 
#include <dlfcn.h> 
int main(){
    void *dlib = dlopen("./libdlib.so", RTLD_NOW); 
    if (!dlib) {
        printf("dlopen failed\n");
        return -1; 
    }
    void (*dfunc) (void) = dlsym(dlib, "dynamic_lib_call"); 
    if (!dfunc) {
        printf("dlsym failed\n");
        return -1; 
    }
    dfunc(); 
    dlclose(dlib); 
    return 0;
}
```

### 程序的平滑无缝升级

对于动态库,升级库,只要保证接口不变就没有多大问题,但是动态库更新,只能更新磁盘文件,对于内存中的数据,是无法直接更新的.

需要使用手工加载动态库

## 避免内存问题

### realloc

- ptr 为 null,size 不为0 ; 等同于 malloc(size)
- ptr 不为 null,size 为0 ; 等同于free(ptr)
- ptr 和 size 都不为0; 等同于 free(ptr),malloc(size)

### 如何防止内存越界

对缓冲区(一般是数组)进行拷贝前,要保证复制的长度不要超过缓冲区的空间大小,例如使用 memcpy 前,要检查目的地址是否有足够的空间

strncat 代替 strcat:`char *strncat(char *dest, const char *src, size_t n);`

要保证dest空间大小至少为 strlen(dest)+n+1,要为'\0'保留位置

strncpy 代替 strcpy:`char *strncpy(char *dest, const char *src, size_t n);`

要保证 src 包含 n个以上字符, dest 包含至少 n+1空间

snprintf代替sprintf: `int snprintf(char *str, size_t size, const char *format, ...);`

使用fgets代替gets:`char *fgets(char *s, int size, FILE *stream);`fgets最多会复制size-1字节到缓存s中，并且会在最后一个字符后面追加'\0'。

### 如何定位内存问题

valgrind作为一个免费且优秀的工具包，提供了很多有用的功能，其中 最有名的就是对内存问题的检测和定位。


## 长跳转 longjmp

longjmp可以实现跨函数的“长跳转”

### setjmp与longjmp的使用

```c
#include <setjmp.h>
int setjmp(jmp_buf env);
void longjmp(jmp_buf env, int val);
```
setjmp用于保存当前栈的上下文，将其保存到参数env中。若返回0值，则为setjmp直接返回的结 果;若返回非0值，则为从longjmp恢复栈空间时返回的结果。

longjmp用于将上下文恢复至env保存的状态，参数val用于作为恢复点setjmp的返回值。一般情况 下，保存的jmp_buf env为全局变量。跳转一次后，保存的env上下文环境就会失效。

```c
#include <stdlib.h> #include <stdio.h>
#include <setjmp.h>
static jmp_buf g_stack_env;
static void func1(void); 
static void func2(void); 
int main(void)
{
    if (0 == setjmp(g_stack_env)) {
        printf("Normal flow\n"); 
        func1();
    } 
    else { 
        printf("Longjump flow\n");
    }
    return 0; 
}
static void func1(void) {
    printf("Enter func1\n");
    func2(); 
}
static void func2(void) {
    printf("Enter func2\n"); 
    longjmp(g_stack_env, 1); 
    printf("Leave func2\n");
}
Normal flow 
Enter func1 
Enter func2 
Longjump flow
```
在main函数中，使用setjmp将当前的栈环境保存到g_stack_env中，然后调用func1->func2，在func2 中，使用longjmp来恢复保存的栈环境g_stack_env，从而完成“长跳转”。

# 进程控制: 进程的一生

## 进程 ID

每一个进程都有非负整数 pid,通过 getpid 可以获得进程的 pid,getppid 可以获得父进程的 id
```c
#include <sys/types.h> 
#include <unistd.h> 
pid_t getpid(void); 
pid_t getppid(void);
```
linux 中进程号1是 init, 树根,其他进程都是有1派生出来,通过 pstree 可以查看完成的树形结构.

procfs 文件系统在`/proc`下为每个进程创建一个目录,名字是该进程的 pid, 目录下有很多文件,用于记录进程的与进行情况和统计信息

进程的创建于终止,会改变 proc 下子目录.

每一个进程的 id 都是唯一的,id 可以复用,linux 分配 id 的算法是延迟重用,分配给每个新创建今晨的 ID 尽量不予最近终止的进程的 ID 重复.具体方法:
- 用位图记录进程 ID 的分配情况(0为可用,1为已占用)
- 将上次分配的进程 ID 记录到 last_pid 中,分配进程 ID 时,从 last_pid+1开始朝气,从位图中寻找可用的 ID
- 如果找到位图集合的最后一位仍不可用,则回滚到位图集合的起始位置,从头开始找

位图的大小决定了可以同时存在的进程最大个数,在系统中成为 pid_max `/proc/sys/kernel/pid_max` `sysctl -w kernel.pid_max=4194304`来修改最大值,但是内核也设置了硬上限,所以修改的值不能大于他,通常是4194304

启示从头开始并不是从0开始,因为小于300的 pid 为系统进程,不能分配给用于,所以是从300开始找起

## 进程的层次

除了父子进程的树形结构外,还有进程、进程组和会话。

进程组合会话在进程之间形成了两级的层次，进程组是一组相关联的集合，会话是一组相关进程组的集合

进程有了 pid 还有 pgid（进程组 id）还有 sid （会话 id）。默认进程会集成那个父进程的会话 id

```
#include <unistd.h> 
pid_t getpgrp(void); 获取进程组 id
pid_t getsid(pid_t pid);获取会话 id
```

进程组和会话是为了支持shell作业控制而引入的概念。

当有新的用户登录Linux时，登录进程会为这个用户创建一个会话。用户的登录shell就是会话的首 进程。会话的首进程ID会作为整个会话的ID。会话是一个或多个进程组的集合，囊括了登录用户的所 有活动。

在登录shell时，用户可能会使用管道，让多个进程互相配合完成一项工作，这一组进程属于同一 个进程组。

### 进程组

`int setpgid(pid_t pid, pid_t pgid);`找到进程 id 为 pid 的进程,将其进程组 id 修改为 pgid, 如果 pid 的值为0,则表示要修改调用进程的进程组 id, 该接口一般用来创建一个新的进程组

进程组是为了方便管理一组进程,比如发送信号给进程组,那么组内所有进程都会收到该消息.

### 会话

`pid_t setsid(void);`该函数执行流程

1. 创建一个新会话，会话ID等于进程ID，调用进程成为会话的首进程
2. 创建一个进程组，进程组ID等于进程ID，调用进程成为进程组的组长。
3. 该进程没有控制终端，如果调用setsid前，该进程有控制终端，这种联系就会断掉。

## fork

`pid_t fork(void)`

通常父子进程会执行不同的代码.fork 函数向子进程返回0,并将子进程的 id 返回给父进程,如果 fork 失败会返回-1,并且设置 errno.常见错误原因:

- EAGAIN: 超出了容许用户创建的进程上限,也可能是超出了系统容许的进程个数的上限
- ENOMEM: 内存不足
- EMOSYS: 平台不支持 fork

```c
ret = fork(); 
if(ret == 0) {
//此处是子进程的代码分支
}
else if(ret > 0) {
//此处是父进程的代码分支
} else {
// fork失败，执行error_handle
```
fork 之后谁先获得 CPU 资源,而率先执行呢?

内核2.6.32开始,默认父进程在成为 fork 之后优先调度的对象,提高性能

### fork 之后父子进程的内存关系

fork 之后子进程完全拷贝了父进程的地址空间,包括堆、栈、代码段等。

glibc 中的 exec 系列函数会丢弃现存的程序代码段，并构建新的数据段、堆、栈。调用 fork 之后，子进程几乎总是通过 exec 系列函数来执行新的程序。

所以 fork 时候不应该立即复制父进程数据，linux 使用了写时复制，子进程只拷贝父进程的页表项，标记为制度，一旦内存页有修改，那么立即执行缺页异常，内核为子进程中对应页面创建一个新的物理页面，并将真正的内容复制到新的物理页中

### fork 之后父子进程与文件的关系

父进程打开的所有文件,子进程也是可以操作的,默认父子进程公用文件的偏移量.

但是如果 open 函数使用O_CLOSEXEC标志位,那么掉公用 exec 时会自动关闭对应的文件,

FD_CLOSEXEC(open时，带上O_CLOSEXEC标志位)标志位的文件,在子进 程调用exec家族函数时会将相应的文件关闭.

### 文件描述符复制的内核实现


## vfork不在使用

## daemon 进程的创建

daemon一般使用 stop 命令停止,或者通过信号将其杀死。daemon 一般以 d 结尾

创建 daemon 进程的步骤：

### 1. 执行 fork 函数，父进程退出，子进程继续

父进程可能是进程组的组长，从而不能够执行后面要执行的 setsid 函数，子进程继承了父进程的进程组 ID，并且拥有自己的进程ID，一定不会是进程组的组长，所以子进 程一定可以执行后面要执行的setsid函数。

### 2. 子进程执行如下三个步骤，以摆脱与环境的关系

1. 修改进程的当前目录为根目录(/) `chdir("/")`
>这样做是有原因的，因为daemon一直在运行，如果当前工作路径上包含有根文件系统以外的其他 文件系统，那么这些文件系统将无法卸载。因此，常规是将当前工作目录切换成根目录，当然也可以 是其他目录，只要确保该目录所在的文件系统不会被卸载即可

2. 调用setsid函数。这个函数的目的是切断与控制终端的所有关系，并且创建一个新的会话
> 这一步比较关键，因为这一步确保了子进程不再归属于控制终端所关联的会话。因此无论终端是 否发送SIGINT、SIGQUIT或SIGTSTP信号，也无论终端是否断开，都与要创建的daemon进程无关，不 会影响到daemon进程的继续执行。

3. 设置文件模式创建掩码为0。`umask(0)`
> 这一步的目的是让daemon进程创建文件的权限属性与shell脱离关系。因为默认情况下，进程的 umask来源于父进程shell的umask。如果不执行umask(0)，那么父进程shell的umask就会影响到daemon 进程的umask。如果用户改变了shell的umask，那么也就相当于改变了daemon的umask，就会造成daemon 进程每次执行的umask信息可能会不一致。

### 3.再次执行fork，父进程退出，子进程继续
执行完前面两步之后，可以说已经比较圆满了:新建会话，进程是会话的首进程，也是进程组的 首进程。进程ID、进程组ID和会话ID，三者的值相同，进程和终端无关联。那么这里为何还要再执行 一次fork函数呢?
原因是，daemon进程有可能会打开一个终端设备，即daemon进程可能会根据需要，执行类似如下 的代码:
int fd = open("/dev/console", O_RDWR);

### 4.关闭标准输入(stdin)、标准输出(stdout)和标准错误(stderr)

关闭了之后，会打开/dev/null，并执行dup2函数，将0、1和2重定向 到/dev/null。这个重定向是有意义的，防止了后面的程序在文件描述符0、1和2上执行I/O库函数而导致 报错。

对于C语言而言，glibc提供了daemon函数，从而帮我们将程序转化成daemon进
程。
`int daemon(int nochdir, int noclose);`
- nochdir:0:将当前工作目录切换到/。
- noclose:0:将标准输入、标准输出和标准错误重定向到/dev/null。

通常使用`daemon(0,0)`

## 进程的终止

在不考虑线程的情况下，进程的退出有以下5种方式。 正常退出有3种:
- 从main函数return返回
- 调用exit
- 调用_exit 
- 调用abort 
- 接收到信号，由信号终止

### _exit

`void _exit(int status);`

_exit函数中status参数定义了进程的终止状态，父进程可以通过wait()来获取该状态值。

虽然status是int型，但是仅有低8位可以被父进程所用

退出状态

- 0 ：成功退出
- 1~125：命令为成功退出，具体含义有个字的命令来定义
- 126：命令找到了，文件无法执行
- 127：命令找不到
- &gt;128：命令收到信号而死亡

`_exit` 通过 `exit_group`系统调用，执行内核清理工作

### exit

`void exit(int status);`

exit最后也会调用 _exit ，他的执行顺序是：
1. 执行 atexit 函数或 on_exit 定义的清理函数
2. 关闭打开的六，所有缓冲的数据均被写入，通过 tmpfile 创建的文件会被删除
3. 调用_exit

无论是调用return返回还是调用exit返回，缓冲区里的数 据都会被冲刷，exit()函数首先执行的是用户注册的清理函数，然后才执行了缓冲区的冲刷。存在临时文件，exit函数会负责将临时文件删除。最后调用了_exit()函数，走向内核清理。

### return 退出

调用main() 的运行时函数会将main的返回值当作exit的参数

## 等待子进程

### 僵尸进程
僵尸进程依然保留的资源 有进程控制块task_struct、内核栈等。这些资源不释放是为了提供一些重要的信息，比如进程为何退 出，是收到信号退出还是正常退出，进程退出码是多少，进程一共消耗了多少系统CPU时间，多少用 户CPU时间，收到了多少信号，发生了多少次上下文切换，最大内存驻留集是多少，产生多少缺页中 断?等等

进程退出后，会保留少量的资 源，等待父进程前来收集这些信息。一旦父进程收集了这些信息之后(通过调用下面提到的 wait/waitpid等函数)，这些残存的资源完成了它的使命，就可以释放了，进程就脱离僵尸状态，彻底 消失了。

制造一个僵尸进程是一件很容易的事情，只要父进程调用fork创建子进 程，子进程退出后，父进程如果不调用wait或waitpid来获取子进程的退出信息，子进程就会沦为僵尸进程。

```c
#include <stdio.h> 
#include <stdlib.h> 
#include <sys/types.h> 
#include <unistd.h> 
int main()
{
	pid_t pid;
	pid=fork(); 
	if(pid<0)
	{
		printf("error occurred!\n");
	}
	else if(pid==0) {
		exit(0);
	}
	else{
		sleep(300);
		wait(NULL); 
	}
	return 0; 
}
```
父进程休眠300秒后才会调用wait来获取子进程的退出信息，而子进程退出之后会变成僵尸状态，等待父进程来获取退出信息。在这300秒左右的时间里，子进程就是一个僵尸进程。

清除僵尸进程有以下两种方法:
- 父进程调用wait函数，为子进程“收尸”。 
- 父进程退出，init进程会为子进程“收尸”。

如果我们不关心子进程的退出状态，就应该将父进程对SIGCHLD的处理函数设置为SIG_IGN，或 者在调用sigaction函数时设置SA_NOCLDWAIT标志位。这两者都会明确告诉子进程，父进程很“绝 情”，不会为子进程“收尸”。子进程退出的时候，内核会检查父进程的SIGCHLD信号处理结构体是否设 置了SA_NOCLDWAIT标志位，或者是否将信号处理函数显式地设为SIG_IGN。如果是，则autoreap为 true，子进程发现autoreap为true也就“死心”了，不会进入僵尸状态，而是调用release_task函数“自行了 断”了。

对于创建了很多子进程的应用来说，知道子进程的返回值是有意义的。比如说父进程维护一个进 程池，通过进程池里的子进程来提供服务。当子进程退出的时候，父进程需要了解子进程的返回值来 确定子进程的“死因”，从而采取更有针对性的措施。

### 等待子进程之wait()

wait()函数来获取子进程的退出状态:`pid_t wait(int *status);`

父进程先调用wait()函数，调用时并无子进程退出，该函数调用就会陷入阻塞状态，直到某个子进程退出

一个进程如何等待所有的子进程退出呢?wait()函数返回有三种可能性:

wait()函数存在一定的局限性:
- 不能等待特定的子进程
- 如果不存在子进程退出，wait()只能阻塞，有些时候，仅仅是想尝试获取退出子进程的退出状态，如果不存在子进程退出就立刻返回，不需要阻塞等待，类似于trywait的概念。wait()函数没有提供trywait的接口
- wait()函数只能发现子进程的终止事件，如果子进程因某信号而停止，或者停止的子进程收到SIGCONT信号又恢复执行，这些事件 wait()函数是无法获知的。换言之，wait()能够探知子进程的死亡，却不能探知子进程的昏迷(暂停)，也无法探知子进程从昏迷中苏醒 (恢复执行)。

### 等待子进程之waitpid()

`pid_t waitpid(pid_t pid, int *status, int options);`
- pid>0:表示等待进程ID为pid的子进程，也就是上文提到的精确打击的对象
- pid=0:表示等待与调用进程同一个进程组的任意子进程;因为子进程可以设置自己的进程组，所以某些子进程不一定和父进程归属于同一个进程组，这样的子进程，waitpid函数就毫不关心了。
- pid=-1:表示等待任意子进程，同wait类似。waitpid(-1，&status，0)与wait(&status)完全等价。
- pid<-1:等待所有子进程中，进程组ID与pid绝对值相等的所有子进程。

wait函数和waitpid函数调用的都是wait4系统调用

### 等待子进程之waitid()

waitpid函数是wait函数的超集，wait函数能干的事情。glibc封装了waitid系统调用从而实现了 waitid函数。

`int waitid(idtype_t idtype, id_t id,siginfo_t *infop, int options);`

- idtype==P_PID:精确打击，等待进程ID等于id的进程。
- idtype==P_PGID:在所有子进程中等待进程组ID等于id的进程。
- idtype==P_ALL:等待任意子进程，第二个参数id被忽略。

options参数是下面标志位的按位或:
- WEXITED:等待子进程的终止事件。
- WSTOPPED:等待被信号暂停的子进程事件。
- WCONTINUED:等待先前被暂停，但是被SIGCONT信号恢复执行的子进程。

## EXEC

整个exec家族有6个函数，这些函数都是构建在execve系统调用之上的，该系统调用的作用是，将 新程序加载到进程的地址空间，丢弃旧有的程序，进程的栈、数据段、堆栈等会被新程序替换。


# 进程控制: 状态、调度、优先级

Linux下，进程的状态有以下7种：

- "R (running)",
- "S (sleeping)",
- "D (disk sleep)", 
- "T (stopped)",
- "t (tracing stop)", 
- "Z (zombie)",
- "X (dead)",
- "x (dead)",
- "K (wakekill)",
- "W (waking)",


**可运行状态（TASK_RUNNING）**

处于可运行状态的进程是进程调度的对象,根据进程所属调度类别的不同，可运行状态的进程也会位于不同的队列上:如果是实时进程(属于实 时调度类)，则根据优先级的情况，落在相应的优先级的队列上;如果是普通进程(属于完全公平调度类)，则根据虚拟运行时间的大小，落 在红黑树的相应位置上。这样进程调度器就可以根据一定的算法从运行队列上挑选合适的进程来使用CPU资源。
`real time != user time+sys time` cpu使用率：`cpu_usage = ((user time) + (sys time))/(real time)`
cpu_usage如果大于1，则表示该进程是计算密集型(CPU bound)的进程，且cpu_usage的值越大，表示越充分地利用 了多处理器的并行运行优势;如果cpu_usage的值小于1，则表示进程为I/O密集型(I/O bound)的进程，多核并行的优势并不明显。

进程运行了多久，内核态CPU时间和用户态CPU时间分别是多少在/proc/PID/stat中提供了相关的信息

系统提供了pidstat命令，通过该命令也可以获取到各个进程的CPU使用情况

**可中断睡眠状态和不可中断睡眠状态**




# 信号

# 理解 Linux 线程 1

# 理解 Linux 线程 2

# 进程间通信: 管道

# 进程间通信:System V IPC

# 进程间通信:POSIX IPC

# 网络通信:连接的建立

# 网络通信:数据报文的发送

# 网络通信:数据报文的接收

# 编写安全无错代码


