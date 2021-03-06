from django.shortcuts import render, redirect
from django.urls import reverse
from django.views.generic import View
from user.models import User, Address
from goods.models import GoodsSKU
from itsdangerous import TimedJSONWebSignatureSerializer as Serializer
from itsdangerous import SignatureExpired
from django.conf import settings
from django.http import HttpResponse
from django.contrib.auth import authenticate, login, logout
from utils.mixin import LoginRequiredMixin
from django.core.mail import send_mail
from celery_tasks.tasks import send_register_active_email
from django_redis import get_redis_connection
from order.models import OrderInfo, OrderGoods
from django.core.paginator import Paginator
import re
# Create your views here.


def register(request):
    """显示注册页面"""
    if request.method == 'GET':
        # 显示注册页面
        return render(request, 'register.html')
    else:
        # 接收数据
        user_name = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据的校验
        if not all([user_name, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验正则
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=user_name)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:  # 用户名存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 进行业务的处理： 用户注册
        user = User.objects.create_user(user_name, email, password)
        user.is_active = 0
        user.save()

        # 返回应答,跳转首页
        return redirect(reverse('goods:index'))


def register_handle(request):
    """进行注册的处理"""
    # 接收数据
    user_name = request.POST.get('user_name')
    password = request.POST.get('pwd')
    email = request.POST.get('email')
    allow = request.POST.get('allow')
    # 进行数据的校验
    if not all([user_name, password, email]):
        # 数据不完整
        return render(request, 'register.html', {'errmsg': '数据不完整'})

    # 校验正则
    if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
        return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

    if allow != 'on':
        return render(request, 'register.html', {'errmsg': '请同意协议'})

    # 校验用户名是否重复
    try:
        user = User.objects.get(username=user_name)
    except User.DoesNotExist:
        # 用户名不存在
        user = None
    if user:  # 用户名存在
        return render(request, 'register.html', {'errmsg': '用户名已存在'})
    # 进行业务的处理： 用户注册
    user = User.objects.create_user(user_name, email, password)
    user.is_active = 0
    user.save()

    # 返回应答,跳转首页
    return redirect(reverse('goods:index'))


class RegisterView(View):
    """注册"""
    def get(self, request):
        """显示注册页面"""
        return render(request, 'register.html')

    def post(self, request):
        """进行注册"""
        # 接收数据
        user_name = request.POST.get('user_name')
        password = request.POST.get('pwd')
        email = request.POST.get('email')
        allow = request.POST.get('allow')
        # 进行数据的校验
        if not all([user_name, password, email]):
            # 数据不完整
            return render(request, 'register.html', {'errmsg': '数据不完整'})

        # 校验正则
        if not re.match(r'^[a-z0-9][\w.\-]*@[a-z0-9\-]+(\.[a-z]{2,5}){1,2}$', email):
            return render(request, 'register.html', {'errmsg': '邮箱格式不正确'})

        if allow != 'on':
            return render(request, 'register.html', {'errmsg': '请同意协议'})

        # 校验用户名是否重复
        try:
            user = User.objects.get(username=user_name)
        except User.DoesNotExist:
            # 用户名不存在
            user = None
        if user:  # 用户名存在
            return render(request, 'register.html', {'errmsg': '用户名已存在'})
        # 进行业务的处理： 用户注册
        user = User.objects.create_user(user_name, email, password)
        user.is_active = 0
        user.save()

        # 发送激活邮件，包含激活的链接：http://127.0.0.1:8000/user/active/1
        # 激活链接中需要包含用户的身份信息，并且要把身份信息进行加密
        # 加密用户的身份信息，生成激活的token
        serializer = Serializer(settings.SECRET_KEY, 3600)  # 一小时后过期
        info = {'confirm': user.id}
        token = serializer.dumps(info)  # bytes需要转成string
        token = token.decode('utf8')  # 默认可以省略urf8
        # 发邮件
        send_register_active_email.delay(email, user_name, token)

        # 返回应答,跳转首页
        return redirect(reverse('goods:index'))


class ActiveView(View):
    """用户激活"""
    def get(self, request, token):
        """进行用户激活"""
        # 进行解密。获取要激活的用户信息
        serializer = Serializer(settings.SECRET_KEY, 3600)
        try:
            info = serializer.loads(token)
            user_id = info['confirm']
            # 根据id获取用户信息
            user = User.objects.get(id=user_id)
            user.is_active = 1
            user.save()
            # 跳转到登录页面
            return redirect(reverse('user:login'))
        except SignatureExpired as e:
            # 激活链接已过期
            return HttpResponse('激活链接已过期')


# /user/login
class LoginView(View):
    """登录"""
    def get(self, request):
        """显示登录页面"""
        # 判断是否记住用户名
        if 'username' in request.COOKIES:
            username = request.COOKIES.get('username')
            checked = 'checked'
        else:
            username = ''
            checked = ''
        return render(request, 'login.html', {'username': username, 'checked': checked})

    def post(self, request):
        """登录的校验"""
        # 接受数据
        username = request.POST.get('username')
        password = request.POST.get('pwd')
        # 校验数据
        if not all([username, password]):
            return render(request, 'login.html', {'errmsg': '数据不完整'})
        # 业务处理
        user = authenticate(username=username, password=password)  # 它会自动关联数据库的is_active
        # AUTHENTICATION_BACKENDS = ['django.contrib.auth.backends.AllowAllUsersModelBackend'] 添加解决问题
        if user is not None:
            if user.is_active:
                # 用户已激活
                # 记录登录状态
                login(request, user)
                # 获取登录后索要跳转到的地址,默认跳转到首页
                next_url = request.GET.get('next', reverse('goods:index'))
                response = redirect(next_url)
                # 判断是否需要记住用户名
                remember = request.POST.get('remember')
                if remember == 'on':
                    # 记住用户名
                    response.set_cookie('username', username, max_age=7*24*3600)
                else:
                    response.delete_cookie('username')
                return response
            else:
                return render(request, 'login.html', {"errmsg": '账户未激活'})
        else:
            return render(request, 'login.html', {"errmsg": '用户名或者密码错误'})


# /user/logout
class LogoutView(View):
    """页面退出登录"""
    def get(self, request):
        """退出登录"""
        # 清楚用户的session信息
        logout(request)
        # 跳转到首页
        return redirect(reverse('goods:index'))


# user
class UserInfoView(LoginRequiredMixin, View):
    """用户中心信息页"""
    def get(self, request):
        """显示"""
        # page='user'
        # 如果用户为登录-》AnonymousUser的一个实例
        # 如果用户登录就是一个User类的实例
        # request.user.is_authenticated()

        # 获取用户的个人信息
        user = request.user
        address = Address.objects.get_default_address(user)
        # 获取用户的历史浏览记录
        # from redis import StrictRedis
        # StrictRedis(host='127.0.0.1', port=6379, db=1)
        con = get_redis_connection('default')
        history_key = 'history_%d' % user.id
        # 获取用户最新浏览的5条商品
        sku_ids = con.lrange(history_key, 0, 4)
        # 从数据库中查询用户浏览的商品的集体信息
        # goods_li = GoodsSKU.objects.filter(id__in=sku_ids)

        goods_li = []
        for id in sku_ids:
            goods = GoodsSKU.objects.get(id=id)
            goods_li.append(goods)
        # 组织上下文
        context = {'page': 'user',
                   'address': address,
                   'goods_li': goods_li}
        # 除了你给模板文件传递的模板变量之外，django框架会把request.user也传递给模板文件
        return render(request, 'user_center_info.html', context)


# user/order
class UserOrderView(LoginRequiredMixin, View):
    """用户中心订单页"""
    def get(self, request, page):
        """显示"""
        # page='order'
        # 获取用户的订单信息
        user = request.user
        orders = OrderInfo.objects.filter(user=user).order_by('-create_time')
        # 遍历获取订单商品的信息
        for order in orders:
            # 根据order_id查询订单商品信息
            order_skus = OrderGoods.objects.filter(order_id=order.sku_id)
            # 遍历order_skus计算商品的小计
            for order_sku in order_skus:
                amount = order_sku.count*order_sku.price
                order_sku.amount = amount
            # 保存订单状态标题
            order_status_name = OrderInfo.ORDER_STATUS[order.order_skus]
            # 动态给order增加属性，保存订单商品的信息
            order.order_skus = order_skus
        # 分页
        paginator = Paginator(orders, 1)
        # 获取第page页的内容
        try:
            page = int(page)
        except Exception as e:
            page = 1
        # 页不能超过最大页码
        if page > paginator.num_pages:
            page = 1
        # 获取第page页的Page实例对象
        order_page = paginator.page(page)
        # 进行页面的控制，页面上最多5个页码
        # 1.总也书小于5页，页面上显示所以页面
        # 2.如果当前页是前3页，显示1-5
        # 3.如果当前页是后3页，显示后5页
        # 4.显示当前页的前两页，和后两页
        num_pages = paginator.num_pages
        if num_pages < 5:
            pages = range(1, num_pages + 1)
        elif page <= 3:
            pages = range(1, 6)
        elif num_pages - page <= 2:
            pages = range(num_pages - 4, num_pages - 1)
        else:
            pages = range(page - 2, page + 3)
        # 组织上下文
        context = {'order_page': order_page,
                   'pages': pages,
                   'page': 'order'}
        return render(request, 'user_center_order.html', context)


# user/address
class AddressView(LoginRequiredMixin, View):
    """用户中心地址页"""
    def get(self, request):
        """显示"""
        # page='address'
        # 获取用户的默认收货地址
        user = request.user
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None
        address = Address.objects.get_default_address(user)
        return render(request, 'user_center_site.html', {'page': 'address', 'address': address})

    def post(self, request):
        """地址的添加"""
        # 接受数据
        receiver = request.POST.get('receiver')
        addr = request.POST.get('addr')
        zip_code = request.POST.get('zip_code')
        phone = request.POST.get('phone')
        # 校验数据
        if not all([receiver, addr, phone]):
            return render(request, 'user_center_site.html', {'errmsg': '数据不完整'})
        # 校验手机号
        if not re.match(r'^1[3|4|5|7|8][0-9]{9}$', phone):
            return render(request, 'user_center_site.html', {'errmsg': '手机格式不合法'})
        # 业务处理：地址添加
        # 如果用户与存在默认收货地址，添加的地址不作为默认收获地址，否则作为默认
        user = request.user
        # try:
        #     address = Address.objects.get(user=user, is_default=True)
        # except Address.DoesNotExist:
        #     # 不存在默认收货地址
        #     address = None
        address = Address.objects.get_default_address(user)
        if address:
            is_default = False
        else:
            is_default = True
        # 添加地址
        Address.objects.create(user=user,
                               receiver=receiver,
                               addr=addr,
                               zip_code=zip_code,
                               phone=phone,
                               is_default=is_default)
        # 应答,刷新地址页面
        return redirect(reverse('user:address'))
