from django.shortcuts import render, redirect
from django.views.generic import View
from django.urls import reverse
from goods.models import GoodsSKU
from user.model import Address
from order.model import OrderInfo, OrderGoods
from django_redis import get_redis_connection
from utils.mixin import LoginRequiredMixin
from django.http import JsonResponse
from datetime import datetime

# Create your views here.


# /order/place
class OrderPlaceView(LoginRequiredMixin, View):
    """提交页面显示"""
    def post(self, request):
        """提交订单显示"""
        sku_ids = request.POST.getlist('sku_ids')
        user = request.user
        # 校验参数
        if not sku_ids:
            # 跳转到购物车页面
            return redirect(reverse('cart:show'))

        conn = get_redis_connection('default')
        cart_key = 'cart_%d' % user.id
        skus = []
        total_count = 0
        total_price = 0
        for sku_id in sku_ids:
            # 根据商品的id获取商品的信息
            sku = GoodsSKU.objects.get(id=sku_id)
            count = conn.hget(cart_key, sku_id)
            # 计算商品的小计
            amount = sku.price * int(count)
            # 动态给sku增加属性count ，保存购买商品的数量
            sku.count = count
            sku.amount = amount
            skus.append(sku)
            total_count += count
            total_price += amount
        # 运费：属于一个子系统
        transit_price = 10  # 写死运费
        # 是付款
        total_pay = transit_price + total_price
        # 获取用户的收件地址
        addrs = Address.objects.filter(user=user)
        sku_ids = ','.join(sku_ids)
        context = {'skus': skus,
                   'total_count': total_count,
                   'total_price': total_price,
                   'transit_price': transit_price,
                   'total_pay': total_pay,
                   'sku_ids': sku_ids,
                   'addrs': addrs}
        return render(request, 'place_order.html', context)


class OrderCommitView(View):
    def post(self, request):
        """订单创建"""
        # 判断用户是否登录
        user = request.user
        if not user.is_authenticated:
            return JsonResponse({'res': 0, 'errmsg': '用户未登录'})

        addr_id = request.POST.get('addr_id')
        pay_method = request.POST.get('pay_method')
        sku_ids = request.POST.get('sku_ids')
        if not all([addr_id, pay_method, sku_ids]):
            return JsonResponse({'res': 1, 'errmsg': '参数不完整'})
        if pay_method not in OrderInfo.PAY_METHODS.keys():
            return JsonResponse({'res': 2, 'errmsg': '非法的校验方式'})

        try:
            addr = Address.objects.get(id=addr_id)
        except Address.DoesNotExist:
            return JsonResponse({'res': 3, 'errmsg': '地址非法'})
        # 向df_order_info表中添加一条记录
        order_id = datetime.now().strftime('%Y%m%d%H%M%S') + str(user.id)
        transit_price = 10
        total_count = 0
        total_price = 0
        order = OrderInfo.objects.create(order_id=order_id,
                                 user=user,
                                 addr=addr,
                                 pay_method=pay_method,
                                 total_count=total_count,
                                 total_price=total_price,
                                 transit_price=transit_price)
        sku_ids = sku_ids.split[',']
        conn = get_redis_connection('dafault')
        cart_key = 'cart_%d' % user.id
        for sku_id in sku_ids:
            # 获取商品的信息
            try:
                sku = GoodsSKU.objects.get(id=sku_id)
            except:
                return JsonResponse({'res': 4, 'errmsg': '商品不存在'})
            # 从redis中获取用户所要购买的商品的数量
            count = conn.hget(cart_key, sku_id)
            OrderGoods.objects.create(order=order,
                                      sku=sku,
                                      count=count,
                                      price=sku.price)
            # todo 更新商品的库存和销量
            sku.stock -= int(count)
            sku.sales += int(count)
            sku.save()
            # 累加计算订单商品的总数量总价格
            amount = sku.price * int(count)
            total_count += int(count)
            total_price += amount
        # 更新订单信息表中的商品总数量，总价格
        order.total_count = total_count
        order.total_price = total_price
        order.save()
        # 清楚用户购物车
        conn.hdel(cart_key, *sku_ids)
        return JsonResponse({'res': 4, 'errmsg': '创建成功'})
