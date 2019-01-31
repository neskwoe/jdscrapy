# -*- coding: utf-8 -*-

import scrapy
import re
import logging
import json
import requests
from scrapy.selector import Selector
from scrapy.http import Request
from jdscrapy.items import CategoriesItem


key_word = ['book', 'e', 'channel', 'mvd', 'list']
Base_url = 'https://list.jd.com'

class SpiderCsdnSpider(scrapy.Spider):

    name = 'jdscrapy'

    allowed_domains = ['jd.com']

    start_urls = ['https://www.jd.com/allSort.aspx']

    def start_requests(self):

        for url in self.start_urls:

            yield Request(url=url, callback=self.parse_product_cat)


    def parse_product_cat(self, response):

        """获取分类页"""

        selector = Selector(response)

        try:

            texts = selector.xpath(

                '//div[@class="category-item m"]/div[@class="mc"]/div[@class="items"]/dl/dd/a').extract()

            for text in texts:

                items = re.findall(r'<a href="(.*?)" target="_blank">(.*?)</a>', text)

                for item in items:

                    if item[0].split('.')[0][2:] in key_word:  #根据网页，所有product 类型连接都应该在keyword 里面

                        if item[0].split('.')[0][2:] != 'list':

                            cat_value = Request(url='https:' + item[0], callback=self.parse_product_cat)

                            yield cat_value

                        else:

                            categoriesItem = CategoriesItem()

                            categoriesItem['name'] = item[1]

                            categoriesItem['url'] = 'https:' + item[0]

                            categoriesItem['_id'] = item[0].split('=')[1].split('&')[0]

                            yield categoriesItem

                            yield Request(url='https:' + item[0], callback=self.parse_product_list)

        except Exception as e:

            print('error:', e)

    def parse_product_list(self, response):

        """分别获得商品的地址和下一页地址"""

        meta = dict()

        meta['category'] = response.url.split('=')[1].split('&')[0]

        selector = Selector(response)

        texts = selector.xpath('//*[@id="plist"]/ul/li/div/div[@class="p-img"]/a').extract()

        for text in texts:

            items = re.findall(r'<a target="_blank" href="(.*?)">', text)

            yield Request(url='https:' + items[0], callback=self.parse_product_list, meta=meta)

        # next page

        next_list = response.xpath('//a[@class="pn-next"]/@href').extract()

        if next_list:

            # print('next page:', Base_url + next_list[0])

            yield Request(url=Base_url + next_list[0], callback=self.parse_product_list)

    def parse_product(self, response):

        """商品页获取title,price,product_id"""

        category = response.meta['category']

        ids = re.findall(r"venderId:(.*?),\s.*?shopId:'(.*?)'", response.text)

        if not ids:

            ids = re.findall(r"venderId:(.*?),\s.*?shopId:(.*?),", response.text)

        vender_id = ids[0][0]

        shop_id = ids[0][1]

        # shop

        shopItem = ShopItem()

        shopItem['shopId'] = shop_id

        shopItem['venderId'] = vender_id

        shopItem['url1'] = 'http://mall.jd.com/index-%s.html' % (shop_id)

        try:

            shopItem['url2'] = 'https:' + response.xpath('//ul[@class="parameter2 p-parameter-list"]/li/a/@href').extract()[0]

        except:

            shopItem['url2'] = shopItem['url1']

        name = ''

        if shop_id == '0':

            name = '京东自营'

        else:

            try:

                name = response.xpath('//ul[@class="parameter2 p-parameter-list"]/li/a//text()').extract()[0]

            except:

                try:

                    name = response.xpath('//div[@class="name"]/a//text()').extract()[0].strip()

                except:

                    try:

                        name = response.xpath('//div[@class="shopName"]/strong/span/a//text()').extract()[0].strip()

                    except:

                        try:

                            name = response.xpath('//div[@class="seller-infor"]/a//text()').extract()[0].strip()

                        except:

                            name = u'京东自营'

        shopItem['name'] = name

        shopItem['_id'] = name

        yield shopItem

        productsItem = ProductsItem()

        productsItem['shopId'] = shop_id

        productsItem['category'] = category

        try:

            title = response.xpath('//div[@class="sku-name"]/text()').extract()[0].replace(u"\xa0", "").strip()

        except Exception as e:

            title = response.xpath('//div[@id="name"]/h1/text()').extract()[0]

        productsItem['name'] = title

        product_id = response.url.split('/')[-1][:-5]

        productsItem['_id'] = product_id

        productsItem['url'] = response.url

        # description
        desc = response.xpath('//ul[@class="parameter2 p-parameter-list"]//text()').extract()

        productsItem['description'] = ';'.join(i.strip() for i in desc)

        # price
        response = requests.get(url=price_url + product_id)

        price_json = response.json()

        productsItem['reallyPrice'] = price_json[0]['p']

        productsItem['originalPrice'] = price_json[0]['m']

        # 优惠
        res_url = favourable_url % (product_id, shop_id, vender_id, category.replace(',', '%2c'))

        # print(res_url)
        response = requests.get(res_url)

        fav_data = response.json()

        if fav_data['skuCoupon']:

            desc1 = []

            for item in fav_data['skuCoupon']:

                start_time = item['beginTime']

                end_time = item['endTime']

                time_dec = item['timeDesc']

                fav_price = item['quota']

                fav_count = item['discount']

                fav_time = item['addDays']

                desc1.append(u'有效期%s至%s,满%s减%s' % (start_time, end_time, fav_price, fav_count))

            productsItem['favourableDesc1'] = ';'.join(desc1)

        if fav_data['prom'] and fav_data['prom']['pickOneTag']:

            desc2 = []

            for item in fav_data['prom']['pickOneTag']:

                desc2.append(item['content'])

            productsItem['favourableDesc1'] = ';'.join(desc2)

        data = dict()

        data['product_id'] = product_id

        yield productsItem

        yield Request(url=comment_url % (product_id, '0'), callback=self.parse_comments, meta=data)
