from django.shortcuts import render
from django.views.generic import View
from django.http import JsonResponse
from goods.models import GoodsSKU
from utils.mixin import LoginRequiredMixin
from django_redis import get_redis_connection

# Create your views here.


# ajax发起的请求都在后台，在浏览器中看不到效果，所以不能用未登录跳转到登录页面的操作
class CartAddView(View):
    """购物车记录添加"""
    def post(self, request):
        """购物车记录添加"""
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '请登录'})
        # 接受数据
        sku_id = request.POST.get('sku_id')
        count = request.POST.get('count')
        # 数据的校验
        if not all([sku_id, count]):
            return JsonResponse({'res': 1, 'errmsg': '数据不完整'})
        # 校验添加的商品数量
        try:
            count = int(count)
        except Exception as e:
            return JsonResponse({'res': 2, 'errmsg': '商品数目出错'})
        # 校验商品是否存在
        try:
            sku = GoodsSKU.objects.get(id=sku_id)
        except Exception as e:
            return JsonResponse({'res': 3, 'errmsg': '商品不存在'})
        # 业务的处理，添加购物车记录
        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        # 先尝试获取sku_id的值
        # sky_id 在hash中不存在，hget放回None
        cart_count = conn.hget(cart_key, sku_id)
        if cart_count:
            # 累加购物车中商品的数目
            count += int(cart_count)
        # 校验商品的库存
        if count > sku.stock:
            return JsonResponse({'res': 4, 'errmsg': '商品库存不足'})
        # 设置hash中sku_id对应的值
        conn.hset(cart_key, sku_id, count)
        # 计算购物车商品的条目数
        total_count = conn.hlen(cart_key)
        # 返回应答
        return JsonResponse({'res': 5, 'total_count': total_count, 'errmsg': '添加成功'})


# /cart
class CartInfoView(LoginRequiredMixin, View):
    """过无车页面显示"""
    def get(self, request):
        """显示"""
        user = request.user
        # 获取用户购物车中商品的信息
        conn = get_redis_connection(request, 'default')
        cart_key = 'cart_%d' % user.id
        cart_dict = conn.hgetall(cart_key)
        skus = []
        # 保存用户购物车中商品的总数量和总价格
        total_count = 0
        total_price = 0
        # 遍历商品的信息
        for sku_id, count in cart_dict.items():
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku对象增加属性，保存小计
            sku.amount = amount
            # 动态给sku对象增加属性,保存购物车中对应商品的数量
            sku.count = count
            skus.append(sku)
            total_count += int(count)
            total_price += amount
            context = {'total_count': total_count,
                       'total_price': total_price,
                       'skus': skus}
        return render(request, 'cart.html', context)
