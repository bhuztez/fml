fml是木兰语言的[同人](https://zh.moegirl.org/同人)运行时。根据[关于
“木兰”语言问题的调查与处理意
见](http://www.ict.cas.cn/shye/tzgg/202001/P020200123675380148930.pdf)
文件精神，可以确定MiniLua是精简版的Lua语言的解释器。Lua在葡萄牙语里是
月亮的意思，不难看出木兰是Moo(n) Lan(guage)的音译。而uLang旨在CPython
3.7上实现Lua 5.3的语义，只是现在为了及早发布，离这个目标还比较远。这并
不妨碍fml在uLang的基础上继续开发。

理想中的fml

```
$ fml
> require("python:this")
Now I see
If I wear a mask
I can fool the world
But I cannot fool my heart

Who is that girl I see
Staring straight back at me?
When will my reflection show
Who I am inside?
```

而截至目前，只能运行

```
$ python3 -m unittest -v fml.test
```
