# server/utils/i18n.py
import os
import json
from typing import Dict

# 添加: i18n 模块
class I18N:
    """
    国际化(i18n)管理类，负责加载和提供翻译文本
    """
    def __init__(self, locale_dir: str = 'locales', default_lang: str = 'en_US'):
        self.locale_dir = os.path.join(os.path.dirname(__file__), '..', locale_dir)
        self.default_lang = default_lang
        self.translations: Dict[str, Dict[str, str]] = {}
        self._load_translations()

    def _load_translations(self):
        """加载所有语言文件"""
        if not os.path.isdir(self.locale_dir):
            print(f"[错误] 语言目录不存在: {self.locale_dir}")
            return
        for filename in os.listdir(self.locale_dir):
            if filename.endswith('.json'):
                lang_code = filename[:-5]
                filepath = os.path.join(self.locale_dir, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        self.translations[lang_code] = json.load(f)
                except (json.JSONDecodeError, IOError) as e:
                    print(f"[错误] 加载语言文件失败 {filepath}: {e}")

    def t(self, key: str, lang: str = 'en_US', **kwargs) -> str:
        """
        获取翻译文本
        :param key: 语言文件中的键
        :param lang: 目标语言代码
        :param kwargs: 用于格式化字符串的参数
        :return: 翻译后的字符串
        """
        # Issue #12: 实现服务器消息的国际化 (i18n)
        lang_map = self.translations.get(lang)
        if not lang_map:
            lang_map = self.translations.get(self.default_lang, {})

        message = lang_map.get(key, key)
        
        try:
            return message.format(**kwargs)
        except (KeyError, IndexError):
            # 如果格式化参数不匹配，返回原始模板以帮助调试
            return message

# 添加: 创建一个全局翻译实例
translator = I18N(default_lang='en_US')