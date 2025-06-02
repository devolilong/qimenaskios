from flask import Flask, render_template, request, jsonify
import pendulum as pdlm
import datetime
import pytz
import kinqimen
from kinliuren import kinliuren
import config
from openai import OpenAI
import json
import traceback
import os
from collections import OrderedDict
from config import find_wx_relation
from flask_cors import CORS

app = Flask(__name__)
# 推荐配置：明确允许 capacitor://localhost
CORS(app, resources={r"/*": {"origins": [
    "capacitor://localhost",
    "http://localhost",
    "http://127.0.0.1"
]}})

@app.route('/')
def index():
    # 获取当前时间作为默认值
    now = datetime.datetime.now(pytz.timezone('Asia/Shanghai'))
    default_data = {
        'qimen_datetime': now.strftime("%Y-%m-%dT%H:%M"),  # HTML datetime-local 格式
        'method': 'chabu',  # 默认拆补
        'type': 'shijia'    # 默认时家
    }
    return render_template('index.html', data=default_data)

@app.route('/calculate', methods=['POST'])
def calculate():
    print("🚀 收到请求了")           # 确认请求到达
    print(request.form)             # 打印表单中的所有字段

    try:
        data = request.form

        lang = data.get('lang', 'zh-CN')  # 默认为中文

        info_labels = {
            'zh-CN': {
                "干支": "干支",
                "排局": "排局",
                "节气": "节气",
                "农历月": "农历月",
                "距节气差日数": "距节气差日数",
                "值符": "值符",
                "值使": "值使",
                "天乙": "天乙",
                "时支驿马": "时支驿马",
                "时空": "时空",
                "击刑": "击刑",
                "门迫": "门迫",
                "入墓": "入墓",
                "伏吟": "伏吟",
                "反吟": "反吟"

            },
            'zh-TW': {
                "干支": "干支",
                "排局": "排局",
                "节气": "節氣",
                "农历月": "農曆月",
                "距节气差日数": "距節氣差日數",
                "值符": "值符",
                "值使": "值使",
                "天乙": "天乙",
                "时支驿马": "時支驛馬",
                "时空": "時空",
                "击刑":"擊刑",
                "门迫":"門迫",
                "入墓":"入墓",
                "伏吟":"伏吟",
                "反吟":"反吟"
            },
            'en': {
                "干支": "Heavenly Stems & Earthly Branches",
                "排局": "Structure",
                "节气": "Solar Term",
                "农历月": "Lunar Month",
                "距节气差日数": "Days from Solar Term",
                "值符": "Chief Deity",
                "值使": "Chief Door",
                "天乙": "Tai Yi",
                "时支驿马": "Traveling Horse (Hour)",
                "时空": "Void Branch (Hour)",
                "击刑":"Six Yi Clashing Punishment",
                "门迫":"Men Po",
                "入墓":"Entering Tomb",
                "伏吟":"Fu Yin",
                "反吟":"Fan Yin"
            }
}
        
        qimen_dt = data.get('qimen_datetime')
        if not qimen_dt:
            return jsonify({'status': 'error', 'message': '未填写排盘时间'}), 400

        try:
            dt_obj = datetime.datetime.strptime(qimen_dt, "%Y-%m-%dT%H:%M")
        except ValueError as ve:
            print(f"[解析失败] 排盘时间格式错误：{qimen_dt}")
            return jsonify({'status': 'error', 'message': '排盘时间格式错误，应为 YYYY-MM-DDTHH:MM'}), 400

        y, m, d, h, minute = dt_obj.year, dt_obj.month, dt_obj.day, dt_obj.hour, dt_obj.minute
        qimen_type = data.get('type', 'shijia')  # shijia 或 kejia
        method = data.get('method', 'chabu')  # chabu 或 zhirun
        
        # 排盘方式转换
        pai = 1 if method == 'chabu' else 2
        
        # 获取干支和节气信息
        gz = config.gangzhi(y, m, d, h, minute)
        j_q = config.jq(y, m, d, h, minute)
        lunar_month = dict(zip(range(1,13), config.cmonth)).get(config.lunar_date_d(y,m,d).get("月"))
        
        # 根据类型选择排盘方式
        qimen = kinqimen.Qimen(y, m, d, h, minute)
        if qimen_type == 'shijia':
            qtext = qimen.pan(pai)
        else:
            qtext = qimen.pan_minute(pai)

        print("🔍 qtext keys:", qtext.keys())
        print("📌 qtext['值符值使']:", qtext.get("值符值使"))
            
        # 获取六壬数据
        lr = kinliuren.Liuren(qtext.get("節氣"), lunar_month, gz[2], gz[3]).result(0)
        
        # 准备基本信息
        # 获取马星信息
        yima = qimen.hourhorse()
        # 获取日空和时空
        kong_result = config.daykong_shikong(y, m, d, h, minute)
        daykong = kong_result.get("日空")
        shikong = kong_result.get("時空")

        #获取值符值使
        zfzs_raw = qtext.get("值符值使", {})

        # 值符由：值符天干 + 值符星宮
        zhifu_tiangan = ' '.join(zfzs_raw.get("值符天干", []))
        zhifu_xinggong = ' '.join(zfzs_raw.get("值符星宮", []))
        zhifu_display = f"{zhifu_tiangan} {zhifu_xinggong}".strip()

        # 值使由：值使門宮
        zhishi_mengong = ' '.join(zfzs_raw.get("值使門宮", []))

        original_info = {
            "干支": qtext.get("干支"),
            "排局": qtext.get("排局"),
            "节气": j_q,
            "农历月": config.lunar_date_d(y, m, d).get("農曆月"),
            "距节气差日数": config.qimen_ju_name_zhirun_raw(y,m,d,h,minute).get("距節氣差日數"),
            "值符": zhifu_display,
            "值使": zhishi_mengong,
            "天乙": qtext.get("天乙"),
            "时支驿马": yima,
            "时空": shikong,
            "击刑": qimen.jixing(option=1),
            "门迫": qimen.menpo(option=1),
            "入墓": qimen.tiangan_rumu(option=1),
            "伏吟": qimen.fuyin(option=1),
            "反吟": qimen.fanyin(option=1)
        }

        # 翻译 key，同时格式化 dict 类型为字符串
        translated_info = OrderedDict()
        # 定义展示顺序
        info_order = [
            "干支", "排局", "节气", "农历月", "距节气差日数",
            "值符", "值使", "天乙", "时支驿马", "时空",
            "伏吟", "反吟", "击刑", "门迫", "入墓"
        ]

        translated_info = OrderedDict()
        for k in info_order:
            v = original_info.get(k)
            label = info_labels.get(lang, info_labels["zh-CN"]).get(k, k)

            if isinstance(v, dict):
                # 子结构化格式处理（击刑、入墓等）
                formatted = ""
                for sub_k, sub_v in v.items():
                    if isinstance(sub_v, (list, tuple)):
                        formatted += f"{sub_k}：{sub_v[0]}, {sub_v[1]}\n"
                    else:
                        formatted += f"{sub_k}：{sub_v}\n"
                translated_info[label] = formatted.strip()
            else:
                translated_info[label] = v
        
        # 生成排盘图
        eg = list("巽離坤震兌艮坎乾")
        qd = [qtext.get("地盤").get(i) for i in eg]
        e_to_s = lr.get("地轉天盤")
        e_to_g = lr.get("地轉天將")
        qt = [qtext.get('天盤', {}).get(i) for i in eg]
        god = [qtext.get("神").get(i) for i in eg]
        door = [qtext.get("門").get(i) for i in eg]
        star = [qtext.get("星").get(i) for i in eg]
        md = qtext.get("地盤").get("中")
        
        # 生成排盘文本
        # 生成结构化九宫数据
        eg = list("巽離坤震兌艮坎乾")
        palace_data = {
            name: {
                "神": qtext["神"].get(name),
                "門": qtext["門"].get(name),
                "星": qtext["星"].get(name),
                "天盤": qtext["天盤"].get(name),
                "地盤": qtext["地盤"].get(name),
            }
            for name in eg
        }
        # 中宫单独处理
        palace_data["中"] = {
            "地盤": qtext["地盤"].get("中")
        }

        # 调用DeepSeek API进行解读
        # client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"),base_url="https://api.deepseek.com")
        client = OpenAI(api_key="sk-78a1145dffd84d2f8731c5abb7133060", base_url="https://api.deepseek.com")

        
        # 已处理完排盘逻辑，如：
        # qtext = qimen.pan(pai)
        # lr = kinliuren.Liuren(...)

        # 解析用户的出生信息
        birth_date = data.get('birth_date')
        birth_shichen = data.get('birth_shichen')
        gender = data.get('gender')

        if birth_date:
            try:
                birth_y, birth_m, birth_d = map(int, birth_date.split('-'))
            except ValueError:
                birth_y = birth_m = birth_d = None
        else:
            birth_y = birth_m = birth_d = None

        has_birth_info = birth_y is not None

        now = datetime.datetime.now(pytz.timezone('Asia/Shanghai'))
        local_time_now = now.strftime("%Y年%-m月%-d日")
        palace_data_json = json.dumps(palace_data, ensure_ascii=False, indent=2)


        
        # 初始化 system_prompt
        if lang == 'en':
            system_prompt = f"""You are a professional Qi Men Dun Jia divination expert.

        Important: The user has already cast the chart. You must ONLY interpret based on the chart below. Do NOT recalculate or infer new charts.

        Current real-world time: {local_time_now}
        Use this year as the reference when describing time (e.g., "this year", "next year"), but base analysis strictly on the chart below.

        Provided Chart:
        {palace_data_json}

        Basic Info:
        {translated_info}

        Before interpreting the following Qi Men Dun Jia chart, please pay special attention to the following key aspects and **integrate them holistically into your analysis** rather than listing them item by item:
        - Whether there is a "Fu Yin" or "Fan Yin" structure  
        - Whether a Six Yi Clashing Punishment pattern is formed (based only on Heavenly Stems on the Heaven Plate clashing with the palace Earthly Branch)  
        - Whether there is a "Men Po" (Gate Suppression) situation, where the gate element overcomes the palace element  
        - Whether any Heavenly Stems fall into tomb/storage palaces ("Entering the Tomb" structures)  
        - Whether Void (Empty) or Traveling Horse (Yi Ma) stars appear, indicating instability or movement  

        Please consider these structural features in combination with the **key palace** related to the user's question—focusing on the corresponding deity, door, star, or Heavenly Stem—and analyze how this palace interacts with other major palaces through the **Five Element (Wu Xing) relationships**.
        Five Element (Wu Xing) relationships must be analyzed strictly based on the backend-defined logic. Do not infer based on common sense or general assumptions.

        Based on this integrated assessment, determine the overall auspiciousness of the chart and offer clear, practical guidance tailored to the user.

        ⚠️ Note: When presenting potentially unfavorable results, please use a neutral, objective, and relatively gentle tone.  
        Avoid exaggerated or alarming language. Your goal is to help the user rationally understand the chart without causing unnecessary fear or anxiety."""

        elif lang == 'zh-TW':
            system_prompt = f"""你是一位專業的奇門遁甲老師。

        重要提醒：使用者已排好此盤，請勿重算，只能根據下方提供的內容進行解讀。

        當前真實時間為：{local_time_now}
        提及「今年」「明年」等詞彙時，請以當前年份為準，但分析內容務必以下方排盤為依據。

        排盤內容：
        {palace_data_json}

        基本資訊：
        {translated_info}

        在解讀以下奇門遁甲排盤前，請特別留意以下重點資訊，並將其**綜合融入整體分析**中，而非逐項列舉：
        - 是否存在伏吟、反吟結構  
        - 是否形成六儀擊刑格局（僅看天盤干與所落宮位的地支是否相刑）  
        - 是否出現「門迫」現象（八門五行剋制所落宮位五行）  
        - 是否有天盤干落入墓庫之地（入墓格）  
        - 是否有空亡、驛馬星等代表「動」或「虛」的現象  

        請結合以上結構特徵，以及與使用者問題最相關的**核心門、星、神或天干所落宮位**的實際情況，
        深入分析該宮與其他重要宮位之間的**五行生剋關係**。五行關係請嚴格依照後端提供的判定邏輯進行分析，禁止自行推斷或套用常識。

        在此基礎上，綜合判斷整體格局之吉凶趨勢，並結合現實情境，提出清晰可行的建議。

        ⚠️ 請注意：在表達可能存在的不利結果時，務必使用中性、客觀且相對溫和的語氣。
        避免使用誇張或帶有恐嚇性的措辭，以幫助問事者理性看待解盤內容，避免引起過度焦慮或誤解。"""

        else:
            system_prompt = f"""你是一位專業的奇门遁甲老师。

        重要提醒：用户已完成排盘，你只能基于以下内容进行解读，禁止重新起盘或推盘。

        当前真实时间为：{local_time_now}
        提到"今年""未来"等词语时请以当前阳历年为准，但分析内容必须完全基于以下排盘数据。

        排盘内容：
        {palace_data_json}

        基本信息：
        {translated_info}

        在解读以下奇门遁甲排盘前，请特别留意以下重点信息，并将其**综合融入整体分析**中，而非逐条列举：
        - 是否存在伏吟、反吟结构
        - 是否形成六仪击刑格局（仅看天盘干与落宫地支刑克关系）
        - 是否出现“门迫”现象（八门五行克宫位五行）
        - 是否有天盘干落入墓库之地（入墓）
        - 时空、驿马落宫
        请结合上述结构特征，以及用户问题相关的**核心门、星、神或天干所在宫位**的实际状态，进一步分析这些宫位与其他关键宫位间的**五行生克关系**。
        五行关系请严格依照后端提供的判定逻辑进行分析，禁止自行推断或套用常识。

        在此基础上，判断整体格局的吉凶趋势，并结合实际，提出清晰可行的建议。
        请注意：在表达可能存在的负面结果时，请使用中性、客观且相对柔和的语言。避免使用夸张或恐吓性的字眼，
        以帮助问测者理性理解命盘内容，而不是造成焦虑或恐惧。"""

        # 若提供了出生信息，则补充说明
        if has_birth_info:
            birth_block = ""
            if lang == 'en':
                birth_block = f"""
        The user also provided birth info:
        - Date: {birth_y}-{birth_m}-{birth_d}
        - Hour: {birth_shichen or 'Not specified'}
        - Gender: {"Male" if gender == 'male' else "Female" if gender == 'female' else "Not specified"}

        Based on this, infer the user's year Heavenly Stem (use previous year if before Spring Begins).
        Then identify the palace it may fall into and analyze whether the palace is favorable — consider its interaction with the Chief Deity, Chief Gate, doors, stars, and spirits.
        Focus especially on this palace and how it affects the user.
        """

            elif lang == 'zh-TW':
                birth_block = f"""
        使用者亦提供了出生資訊：
        - 出生日期：{birth_y} 年 {birth_m} 月 {birth_d} 日
        - 出生時辰：{birth_shichen or '未填寫'} 時
        - 性別：{"男" if gender == 'male' else "女" if gender == 'female' else "未填寫"}

        請依據此資訊推算其年命天干（若在立春前請以前一年計），並找出其對應的宮位，結合該宮門、星、神的內容，判斷其在本局中的得勢與否，並詳加說明。
        """

            else:
                birth_block = f"""
        用户还提供了出生信息：
        - 出生日期：{birth_y} 年 {birth_m} 月 {birth_d} 日
        - 出生时辰：{birth_shichen or '未填写'} 时
        - 性别：{"男" if gender == 'male' else "女" if gender == 'female' else "未填写"}

        请根据该信息推断用户的年命天干（若在立春前请以前一年为准），找出其可能对应的落宫，结合该宫门、星、神的吉凶结构，判断命主在此盘中的地位与影响。
        """

            system_prompt += birth_block

        # 用户问题
        user_question = data.get('question', '')
        if user_question:
            if lang == 'en':
                system_prompt += f"\n\nUser's question: {user_question}\nPlease prioritize this in your interpretation."
            elif lang == 'zh-TW':
                system_prompt += f"\n\n使用者問題：{user_question}\n請於解讀中針對此議題給予重點分析。"
            else:
                system_prompt += f"\n\n用户问题：{user_question}\n请在解盘中重点围绕此问题展开。"
        
        palace_data_json = json.dumps(palace_data, ensure_ascii=False, indent=2)

        try:
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": "请根据以上内容详细解读。"}
                ],
                stream=False,
                max_tokens=800,            # 控制输出长度
                temperature=0.7,
                timeout=120               # 控制等待时间（单位是秒）
            )
            explanation = response.choices[0].message.content
        except Exception as e:
            import traceback
            traceback.print_exc()
            print("❌ AI 解读失败：", e)
            explanation = "AI 解读失败，请稍后再试"
        
        interpretation = explanation
        
        
        response = jsonify({
            'status': 'success',
            'basic_info': translated_info or {},
            'palace_data': palace_data or {},
            'interpretation': interpretation or "暂无解读结果",
            'raw_result': qtext or {}
        })
        response.headers.add('Access-Control-Allow-Origin', 'capacitor://localhost')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response
        
    except Exception as e:
        response = jsonify({
                'status': 'error',
                'message': str(e)
        })
        response.headers.add('Access-Control-Allow-Origin', 'capacitor://localhost')
        response.headers.add('Access-Control-Allow-Headers', 'Content-Type')
        response.headers.add('Access-Control-Allow-Methods', 'POST')
        return response, 500

if __name__ == '__main__':
    app.run(debug=True, port=5001)
