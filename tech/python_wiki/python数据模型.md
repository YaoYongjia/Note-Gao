# python数据模型

## **对象,值,类型**

python中所有东西都是对象,python程序中的所有数据要么是对象,要么就是有关系的对象.  

每一个对象都由三个部分组成:标识,类型,值.对象一旦创建,那么标识就不会改变,可以通过`id函数`来获取对象的标识,他会返回一个整数,cpython中这个整数代表内存地址,并且`is`运算符就是比较两个对象的标识.  

对象的类型决定了对象支持哪些操作,`tpye`函数返回一个对象的类型(type本身也是一个对象),对象一旦创建后,**对象的类型也是不可改变的**.  

对象的值如果可变,那么对象就是 **可变对象mutable**,不可改变就是 **不可变对象immutable**,对象的可变性也是有类型决定的,例如:字符串,元组,数字就是不可变的,字典和列表就是可变的

Cpython中来及回收机制是通过引用计数来实现的,并且还提供了其他方案,(,标记清楚,分代回收,参考gc模块);对于`try..except`语句捕获的异常可能会使对象一直存活.

有些对象包含对`外部external`资源的引用,例如打开文件或窗口,当垃圾回收机制回收这些对象时,引用的资源会被释放,但是垃圾回收不能够保证一定发生,所以这些对象通常提供一个明确释放引用资源的方法,通常是`close`方法.强烈建议程序中明确调用此类对象的close方法,通常我们在`try...finally`或者`with`语句中显示关闭

关于容器对象的不可变性,如果一个容器对象不可变,例如:元组.元组的不可变性在于其包含的元素不可更改,这里是不能更改元素的id,但是如果包含的元素是一个可变容器,那么这里是允许修改该元素的值得

## **标准类型体系**

### **None**

他在`__builtin__`字典中,他可以在很多场景中用来标志不存在某个值.如果一个函数没有显示返回一个值得话,那么默认就返回`None`,`operator.truth(None) == False `

### **NotImplemented**

他在`__builtin__`字典中`operator.truth(NotImplemented)==True`

如果一个对想的数值操作方法和富比较方法没有实现,那么该方法应该返回NotImplemented
```python
class MyIntegral(numbers.Integral):
    def __add__(self, other):
        if isinstance(other, MyIntegral):
            return do_my_adding_stuff(self, other)
        elif isinstance(other, OtherTypeIKnowAbout):
            return do_my_other_adding_stuff(self, other)
        else:
            return NotImplemented
```

### **Ellipsis**

`省略符,python3特有,不知怎么玩` ,`operator.truth(Ellipsis)==True`

### **数值类型**

**整数**

整数分为两类:
- int:表示无限范围的数字
- bool:是整数的子类型,只有两个对象`False`和`True`,两个对象的字符串分别是`'False'`和`'True'`

**浮点数**

**复数**

### **序列Sequences**

序列通过非负索引来进行访问,索引位置从0开始,`len`方法放回序列的长度,如果序列长度为`n`,那么索引从`0,1,...,n-1`

序列的切片(slice) `a[i:j]`表示 a 中 `i<=k<j`区间的元素;切片还支持步进,`a[i:j:k]`

内置序列类型:  
- **str**:不可变序列  
- **tuple**:不可变序列
- **bytes**:不可变序列,包含的元素都是8位二进制,也就是一个字节,每个元素的数值范围是`0<=x<=255`,例如:`b'abc'`;内置方法`bytes`可以用来创建该对象,并且通过`decode`方法可以解码为字符串


- **list**:可变序列
- **bytearray**:可变序列,可以通过`bytearray`来创建,与bytes类似,只是他是可变的

### **集合set**

集合是无序的,其中所有元素都是唯一的,并且所有元素本身必须是不可变的.集合可以用来进行快速的判断某个元素是否该集合中.(因为它使用的数据结构与字典类似),支持集合的差,并,交,对称差操作
> 因为集合中的元素都是不可变,通常也就是说,该元素必须实现了`__hash__`方法,如果两个元素的hash值相同,那么认为两个元素是同一个元素,例如`1`和`1.0`就认为是同一个元素

**set**是可变的集合

**frozenset**是不可变集合

### **映射 Mapping**

a[k] 表示获取到通过k进行索引的元素,python中只有一种内置映射类型:**字典**

字典中的key对象不可以是可变数据类型,因为字典并不是用key对象的标识,而是通过key对象的hash值比较key,而可变对象的hash值是不固定的.

### **可调用类型 Callable types**

#### **用户自定的函数对象**

函数的属性:

- `__doc__`:函数的文档字符串,或者是None,可以修改
- `__name__`:函数的名字,可以修改,例如:`test.__name__='test2'`,这里面还是通过test来调用函数,函数对象的默认名字是函数名,(没有发现修改的意义)
- `__qualname__`:带路径的函数名,可以修改,(没有发现修改的意义)
- `__module__`:函数所在的模块名称,可以修改,(没有发现修改的意义)
- `__code__`:编译之后的字节码对象,可以修改,函数真正的执行体就是code对象
```python
def test1():
    print('test1')

def test2(a):
    print(a)

test1()#打印test1

test1.__code__=test2.__code__ 

test1(10)# 10 注意这里test2是要接受参数的
```
> 这里需要参考一下python中函数对象的源代码实现,包括函数的调用过程的源码实现(也就是虚拟机的运行)

- `__closure__`:闭包相关,只读
- `__annotations__`:参数的注释以及return的注释,可修改
- `__kwdefaults__`:命名参数的默认值字典, 可修改

#### **对象的方法**

```python
class A():
    def test(self):
        pass 
    @classmethod
    def ctest(cls):
        pass 

```

对象的方法核心还是function对象,除了具有function除了具有function对象的属性,还包含类与对象的相关属性

`obj.func.__self__`是对象自己  

`obj.func.__func__`是原始函数,例如:`test(self,...)` 可以通过`obj.func.__func__(obj,...)`来调用,只不过python方便方法是直接用`obj.func()`但是底层还是调用的`__func__`函数

`type(obj.func)`返回的是method类型 **而type(Obj.test)**返回的是function类型,说白了方法就是类中的一个函数,`Obj.test(obj)`可以直接使用

`obj.func(1)`等同于`Obj.func(obj,1)`

`obj.classfunc(1)`等同于`Obj.classfunc(1)`等同于`Obj.classfunc.__func__(Obj,1)`

#### **生成器函数**

只要一个函数中定义了`yield`指令,那么这个函数就被称为生成器函数.当调用这个函数的时候总会返回一个迭代器对象`iterator`,调用`iterator.__next__()`会导致函数执行,一直执行到`yield`指令.当这个函数执行了`return`指令或者发生异常,那么会抛出`StopIteration`异常


#### **协程函数**

如果一个函数使用`async def`定义的,那么这个函数就叫协程函数,调用该函数会返回一个协程对象`coroutine`,他可能会包含`await`,`async with`,`async for`

#### **异步生成器**

如果一个函数使用`async def`定义,并且包含了`yield`指令,那么这个函数被调用时会返回异步迭代器,他可以在`async for`语句中使用,来执行函数体.

调用`aiterator.__anext__()`会返回一个`awaitable`他会一直等待yield指令提供一个值.当函执行一个空的`return`指令或发生异常时,`StopAsyncIterrator`异常会抛出

#### **内置函数**

比如`len` 

#### **类**

类也是可调用的,类也是对象,类可以看做一个工厂,用于创建对象,调用类,会先调用类的`__new__`方法来创建对象,然后可能还会调用`__init__()`来初始化对象

#### **类对象**

只要类实现了`__call__`方法,那么该类的实例就是可调用的

## **模块 Module**

模块对象通过`import`或者`importlib.import_module()`或者`__builtin__.__import__`函数来导入
模块X的属性`X.a` 等同于 `X.__dict__['a']`

属性:
- `__name__`:模块的名字
- `__file__`:模块的文件路径

## **自定义的类**

```python
class A():
    a=10
    b=10
a=A()
a.__dict__=={} 
A.__dict__=={
    "a":10,
    "b":10
}
```
A.a等同于`A.__dict__['a']`

- `__name__`:类的名字
- `__dict__`:类的命名空间
- `__bases__`:类的基类

### **类实例**
- `__dict__`:属性字典
- `__class__`:类的名称 


实例的的属性都是在`__dict__`中,如果`__dict__`没有找到该属性,那么会尝试调用,`__getattr__`来查找

给对象添加属性或者删除属性是直接修改对象的属性字典
```python
del a.c 
a.__dict__=={}
a.d=100
a.__dict__=={
    "d":100
}
```
> 如果给对象添加属性名字那么直接王属性字典里面添加键值对,对象的字典属性与类的字典属性是不同的字典对象

**如果对象有`__setattr__`或者`__delattr__`方法,那么就会调用该方法,而不是直接操作属性字典**

```python
A.__setattr__=lambda self,key,value:print(key)
a.s=100 # 这里会打印s
A.__delattr__=lambda self,key:print('del ',key)
del a.s # 这里打印 del s
```
> 类对象可以表现为数值,序列,字典,只要对象拥有对应的特殊方法

###  **IO对象**

可以通过`open`,`os.open`,`os.fdopen`,`makefile`来创建文件对象

`sys.stdin`,`sys.stdout`,`sys.stderr`解释其中的标准输入,输出,与错误流文件.他们是以文本模式打开的,跟随`io.TextIOBase`

### **内置类型**

有些内置类型是暴露给用户的

#### **Code对象**

code对象包含python的代码编译之后的可执行字节码.code对象和function对象的区别在于:function对象明确的包含函数的全局命名空间(function's globals)(就是函数所在的模块),code对象是不包含上下文的.默认值也是保存在函数对象中的,而不是在code对象中,code对象是不可变的而function对象是可变的.并且code对象不包含任何可变对象的引用

特殊属性:
- co_name: 函数的名字
- co_argcount: 位置参数的个数
- co_nlocals: 本地变量和包括函数参数的个数
- co_varnames: 参数名,以及本地变量名 元组
- co_cellvars: 被嵌套函数引用的外部函数的变量 元组
- co_freevars: free变量名的元组 
- co_code: 字节码字符串
- co_consts: 被字节码使用的对象元组
- co_names: 被字节码使用的名字 元组
- co_filename: 字节码所在的被编译的文件
- co_firstlineno: 函数的第一行行号
- co_lntotab: `?`
- co_stacksize: 需要的栈空间大小(包括本地变量)
- co_flags: 给解释器使用,是一个整数,
> flag: 0x04表示函数使用了*args,0x08表示函数使用了**kwargs,0x20表示函数是一个生成器

#### **Frame 对象**

python中模拟函数嵌套调用的对象,起始函数到最后也是变成了,Frame对象来执行的,他是链式结构

属性:
- f_back: 上一个frame对象
- f_code: 字节码对象
- f_locals: 本地变量字典
- f_builtins: 内置变量字典
- f_globals: 全局变量字典
- f_lasti: 字节码字符串对应于code对象的索引

可写属性:
- f_trace: trace对象,
- f_lineno: 当前frame的行号

#### **Traceback 对象**

traceback对象用于跟踪异常,他异常发生时就会创建该对象,因为虚拟机最终执行的函数frame,所以traceback会包含frame相关信息

- tb_frame:当前的frame
- tb_lineno:行号
- tb_lasti: 与f_lasti类似

#### **Slice 切片对象**

常见列表 `a[1:10:2]`,里面使用的就是切片对象,切片对象传递给`__getitem__`方法
还可以通过内置方法`slice`来创建切片对象,
```python
a=range(100)
a[10:20:2] # range(10, 20, 2)
asc=slice(10,20,2)
a.__getitem__(asc) # range(10, 20, 2)
```

#### **Static method 静态方法对象**

通过 `__builtin__.staticmethod`构造函数来创建

#### **Class method 类方法对象**

通过`__builtin__.classmethod`构造函数来创建

## **特殊方法**

类可以通过定义特殊名称的方法来实现特殊的语法操作(例如算数元素,逻辑运算,切片等),比如:`x[i]`其实是调用`type(x).__getitem__(x,i)` ,如果x具有`__getitem__`那么就会调用,否则就抛出`TypeError`或者`AttributeError`

如果把特殊方法设置为None,就相当于禁用了该特殊语法.例如:如果把`__iter__`设置为None,就说明该对象不支持迭代,那么`iter(x)`就会抛出`TypeError`(他不会去查找`__getitem__()`)

### **基本的自定义**

#### **`object.__new__(cls[,...])`**

调用这个方法来创建新的类对象,他是一个静态方法,这个房返回的必须是一个类对象

通常在这个方法中都会调用父类的new方法`super().__new__(cls[,...])`然后在对对象进行修改,然后在返回修改后的对象

new方法返回一个对象,然后会调用这个对象的`__init__(self[,...])`,这里传递进来的参数就是`__new__`接受的参数

如果new没有返回一个对象,那么init方法也不会被调用

#### **`object.__init__(self[,...])`**

init方法不可以返回非None值,否则抛出`TypeError`,可以调用`super().init([,...])`

#### **`object.__del__(self)`**

对象即将被销毁的时候调用,通常叫做析构函数,如果父类有`__del__`方法,那么会先调用父类的del方法

这个方法不保证会被调用,因为很多对象会一直存活

#### **`object.__repr__(self)`**

用于计算`官方`的字符串,如果定义了`__repr__`而没有定义`__str__`那么repr也作为`infomal`字符串

#### **`object.__str__(self)`**

`str(object)`就是调用了`object.__str__` 如果没有定义str方法,那么就会先去调用`__repr__`

#### **`object.__bytes__(self)`**

`bytes(object)`就是调用了`object.__bytes__`用于计算字节字符串

#### **`object.__format__(self,format_spec)`**

`format(object,format_spec)`就是调用`object.__format__(format_spec)`

- `object.__lt__ a<b`
- `object.__gt__ a>b`
- `object.__eq__ a==b`
- `object.__ne__ a!=b`
- `object.__le__ a<=b`
- `object.__ge__ a>=b`

#### **`object.__hash__`**

`hash(object)`就是调用了`object.__hash__` 

**他必须返回一个整数**在64位机器上是8字节的整数,32位机器上是4字节的整数.对于以来与hash值得容器对象(例如:dict,set,frozenset)

如果比较两个对象相等,那么他们的hash值也必须相等

python内置数据类型str,int,tuple都是支持hash的.

**如果一个类没有定义`__eq__`,那么必须定义`__hash__`**

**如果一个对象是可变的,并且实现了`__eq__`,那么他不应该定义`__hash__`方法,因为hash对象不允许使用可变的对象**

用户自定义的类,默认是带`__eq__`和`__hash__`方法的,默认情况下对象与其他对象比较时,返回的都是不想等.并且`obj.__hash__()`返回一个适当的值

如果定义了`__eq__`而没有定义`__hash__`那么`__hash__`被设置为None,也就是不支持hash

#### **`object.bool(self)`**

`bool(object)`就是调用`object.__bool__(self)`他返回False,或者True,如果对象没有`__bool__`那么会尝试调用对象的`__len__()`,如果都没有定义那么返回就是True

### **自定属性获取** 

#### **`object.__getattr__(self,name)`**

要么返回一个值,要么返回`AttributeError`

要结合`object.__getattribute__(self,name)`一起来看

只有当`__getattribute__`返回AttributeError或者在`__getattribute__`主动调用了`__getattr__`,`__getattr__`才会执行.

`getattr(object,'key')`也是先调用`__getattribute__`失败就调用`__getattr__`

#### **`object.__setattr__(self,name,value)`** 

```python
`A.__setattr__=lambda self,x,y:print(x,': ',y)` 

`setattr(a,'s','s')` # s: s

a.m='m' # m: m
```

#### **`object.__delattr__(self,name)`**

`del object.name` 就是调用`就是调用 object.__delattr__(name)`

#### **`object.__dir__(self)`**

`dir(object)`就相当于`object.__dir__()` 必须返回一个序列dir会把返回的序列转换为list并且排序

### **Descriptors**

### **`__slots__`**

`__slots__`允许我们明确的声明数据成员,并且拒绝创建`__dict__`和`__weakref__`(除非明确在`__slots__`或者父类中声明)

#### **`object.__slots__`**

这个变量接受字符串,可迭代对象,或者序列;其中包含的是变量名,`__slots__`会开辟空间用于声明变量并且阻止自动为每一个对象创建`__dict__`和`__weakref__`

#### **关于使用slots**

- 如果没有定义`__slots__`,那么对象的`__dict__`和`__weakref__`会自动创建
- 如果没有`__dict__`变量,那么对象没有办法非`__slots__`中声明的变量赋值;如果想要把`'__dict__'`添加到slots中
- 如果没有定义`__weakref__`变量,python中无法使用弱引用,需要在`__slots__`中定义`'__weakref__'`
- `__slots__`在类层面实现了descriptor
- 父类的`__slots__`在子类中是可见的,但是子类的对象还是有`__dict__`和`__weakref__`除非子类中也定义了`__slots__`
- 如果子类和父类都定义了slots,那么父类中定义的slot在子类中是不可访问的

### **`定义类对象的创建`**

只要一个类继承了某一个父类,那么父类的`__init_subclass__`都会被调用

```python
class A():
    __slots__=['a','b','__dict__']
    def __init_subclass__(cls,default_name,**kwargs):
        super().__init_subclass__(**kwargs)
        cls.default_name=default_name
        print(cls)
class B(A,default_name="Bbb"):
    pass
# 这里打印<class '__main__.B'>
```

### **Metaclasses**

默认情况下,类是通过`type`初始化的,定了类之后,类的body会被执行,
```python
class C():
    print('ddd')
# 这里会打印出ddd
```
可以通过传递metaclass来指定元类
```python
class Meta(type):
    pass

class MyClass(metaclass=Meta):
    pass

class MySubclass(MyClass):
    pass
```
当定义类的指令被执行时,会执行以下几个步骤:
- 处理MRO的入口
- 选择合适的metaclass
- 准备好类的命名空间
- 运行类的body
- 创建类对象

####  处理MRO的入口

如果累的基类中不是type类的对象,那么`__mro_entries__`方法就会执行,这个方法必须返回一个元组,这个元组将用于体检bases

#### 选择合适的metaclass

通过以下几个步骤来找metaclass
- 如果没有明确定义metaclass或者么有定义bases(基类元组),那么使用`type()`
- 如果明确指定了metaclass,但是他不是type的对象那么,该元类直接作为metaclass
- 如果指定了一个type对象作为元类,或者定义了bases,那么最近的metaclass会被使用

#### 准备好类的命名空间

一旦确认好了metaclass之后,然后准备好命名空间,如果metaclass定义了`__preparre__`方法,那么就会调用`namespace=metaclass.__prepare__(name,bases,**kwargs)`(kwargs来自于类的定义)
如果没有`__preparre__`方法,那么namespace是一个空的有序字典(an empty ordered mapping)

#### 执行class body

相当于执行`exec(body,globals(),namespace)`

#### 创建类对象

当执行完类body后,会弹出了命名空间.让后通过`metaclass(name,bases,namespace,**kwds)`(这里的kwds也prepare中的一样)

```python
class OrderedClass(type):

    @classmethod
    def __prepare__(metacls, name, bases, **kwds):
        return collections.OrderedDict()

    def __new__(cls, name, bases, namespace, **kwds):
        result = type.__new__(cls, name, bases, dict(namespace))
        result.members = tuple(namespace)
        return result

class A(metaclass=OrderedClass):
    def one(self): pass
    def two(self): pass
    def three(self): pass
    def four(self): pass

>>> A.members
('__module__', 'one', 'two', 'three', 'four')
```

## **模拟可调用对象**

`object.__call__(self[,...])`

## **模拟容器对象**

`collections.abc.MutableMapping`提供了`__getitem__`,`__setitem__`,`__delitem__`,`keys()`.

可变的序列对象必须支持`append`,`count`,`index`,`extend`,`insert`,`pop`,`remove`,`reverse`,`sort`;

序列对象还应该支持`__add__`,`__radd__`,`__iadd__`,`__mul__`,`__rmul__`,`__imul__`;

建议序列或者映射对象支持`__contains__`来支持`in`操作符;同时建议支持`__iter__`对于映射对象,他映带与`keys()`一样,对于序列对象,应当迭代序列中的值

### `object.__len__(self)`

`len(obj)` 就是 `obj.__len__()` 

如果对想没有定义`__bool__`并且len返回值是0那么就是False

### `object.__length__hint__(self)` python3.4支持
返回的预估的长度,跟实际长度可能有出入

### `object.__getitem__(self,key)`

### `object.__missing__(self,key)`

如果字典的子类对象通过self[key],而可以没在字典中,那么就会被`dict.__getitem__`方法调用

### `object.__reversed__(self)`

`reversed(obj)` 调用 `obj.__reversed__()`  如果对象没有提供`__reversed__`那么就会回退到调用`__len__`和`__getitem__`

### `object.__contains__(self,item)`

返回True或者False

## 模拟数值类型



- `__add__(self, other)`: `+`  `obj1 + obj2`
- `__sub__(self, other)`: `-` `obj1 - obj2`
- `__mul__(self, other)`: `*` `obj1 * obj2`
- `__matmul__(self, other)`: `@` 矩阵乘法 `obj1 @ obj2`
- `__truediv__(self, other)`: `/` `obj1 / obj2`
- `__floordiv__(self, other)`: `//` `obj1 // obj2` 向下取整
- `__mod__(self, other)`: `%` `obj1 % obj2` 取模运算
- `__divmod__(self, other)`: `divmod()` 
- `__pow__(self, other[, modulo])`: `**` `(obj1**obj2)%modulo` 如果没有提供modulo,就忽略
- `__lshift__(self, other)`: `<<` 
- `__rshift__(self, other)`: `>>`
- `__and__(self, other)`: `&`
- `__xor__(self, other)`: `^`
- `__or__(self, other)`: `|`

- `__radd__(self, other)`
- `__rsub__(self, other)`
- `__rmul__(self, other)`
- `__rmatmul__(self, other)`
- `__rtruediv__(self, other)`
- `__rfloordiv__(self, other)`
- `__rmod__(self, other)`
- `__rdivmod__(self, other)`
- `__rpow__(self, other[, modulo])`
- `__rlshift__(self, other)`
- `__rrshift__(self, other)`
- `__rand__(self, other)`
- `__rxor__(self, other)`
- `__ror__(self, other)`

关于add与radd

例如: a+b

首先判断a是否有add方法,如果有那么调用`a.__add__(b)`,如果返回了值,那么结束,如果返回NotImplement,抛出异常
如果a没有add方法,那么判断b是否有radd方法,如果有,那么调用`b.__radd__(a)`,如果返回了值,那么就结束,否则抛出异常

- `__iadd__(self, other)` 
- `__isub__(self, other)`
- `__imul__(self, other)`
- `__imatmul__(self, other)`
- `__itruediv__(self, other)`
- `__ifloordiv__(self, other)`
- `__imod__(self, other)`
- `__idivmod__(self, other)`
- `__ipow__(self, other[, modulo])`
- `__ilshift__(self, other)`
- `__irshift__(self, other)`
- `__iand__(self, other)`
- `__ixor__(self, other)`
- `__ior__(self, other)`

x+=y相当于`x.__iadd__(y)` 如果没有定义iadd那么回到x+y,就是尝试`a.__add__(y)`或者`y.__radd__(x)`


- `__neg__(self)`: `-obj1`
- `__pos__(self)`: `+obj1`
- `__abs__(self)`: `abs(obj1)`
- `__invert__(self)`: `~obj1`
- `__complex__(self)`:`complex()`
- `__int__(self)`:`int`
- `__float__(self)`:`float`
- `__index__(self)`: 必须返回一个整数
- `__round__(self[, ndigits])`: `round(obj)`
- `__trunc__(self)`: `math.trunc(obj)`
- `__floor__(self)`: `math.floor(obj)`
- `__ceil__(self)`: `math.ceil(obj)`
如果没有定义`__int__`那么会调用`__trunc__`

### 上下文管理

`object.__enter__(self)`他的返回值会作为`as`的目标

`object.__exit__(self,ecx_type,exc_value,traceback)`如果没有异常发生,那么三个参数为None,如果有异常发生,并且这个方法想组织异常信息往上层抛出,那么应该返回一个true值,否则异常信息会继续网上走

## 协程

### Awaitable对象

Awaitable对象对象通常实现了`__await__`方法,`async def`返回的协程对象也支持`__await__`方法

`__await__`方法需要返回一个迭代器

### Coroutine对象
Coroutine对象都是Awaitable对象,协程执行过程可以通过调用`__await__()`并且通过迭代的结果进行控制.当协程结束时,迭代器会抛出`StopIteration`

协程还支持其他方法,有点类似于生成器的方法

coroutine.send(value)
coroutine.throw(value)
coroutine.close(value)

### Asynchronous迭代器

异步得带器在`async for`语句中使用,`object.__aiter__(self)`返回异步迭代器,`object.__anext__(self)`必须返回一个awaitable结果,如果没有了就应当抛出`StopAsyncIteration`

```python
class Reader:
    async def readline(self):
        ...

    def __aiter__(self):
        return self

    async def __anext__(self):
        val = await self.readline()
        if val == b'':
            raise StopAsyncIteration
        return val
```

### 异步上下文管理

`object.__aenter__`,`object.__aexit__`









