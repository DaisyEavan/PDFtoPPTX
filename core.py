import sys
from pathlib import Path
import fitz  # PyMuPDF
from pptx import Presentation
from pptx.util import Inches


def get_app_dir():
    """返回应用程序所在目录（开发或打包后均适用）"""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:
        return Path(__file__).resolve().parent


class PDFtoPPTXConverter:
    def __init__(self, pdf_path, template_dir, output_path, target_ratio, zoom=10, cache_dir=None):
        """
        pdf_path: PDF 文件路径
        template_dir: PPT 模板文件夹路径
        output_path: 输出 PPT 文件路径
        target_ratio: 目标比例，如 "16:9"、"4:3"、"16:10"、"A4"
        zoom: 图片缩放倍数，默认 10（极致清晰）
        cache_dir: 缓存图片存放的父目录，默认为软件目录下的 cache 文件夹
        """
        self.pdf_path = Path(pdf_path)
        self.template_dir = Path(template_dir)
        self.output_path = Path(output_path)
        self.target_ratio = target_ratio
        self.zoom = zoom

        # 处理缓存目录
        if cache_dir is None:
            cache_dir = get_app_dir() / "cache"
        self.cache_dir = Path(cache_dir)
        self.temp_pic_dir = self.cache_dir / "pic_temp"

    def run_with_progress(self, progress_callback):
        """
        执行转换，并通过 progress_callback(current, total) 报告进度
        progress_callback: 可调用对象，参数 (当前页序号, 总页数)
        """
        # 先转图片，过程中回调进度
        img_paths, page_count = self._pdf_to_images(progress_callback)
        # 再插入 PPT
        self._images_to_pptx(img_paths)
        return str(self.output_path)

    def _detect_pdf_ratio(self):
        """检测 PDF 第一页的宽高比（可选功能，当前未在 core 中使用）"""
        doc = fitz.open(self.pdf_path)
        page = doc[0]
        width, height = page.rect.width, page.rect.height
        ratio = width / height
        if abs(ratio - 1.333) < 0.1:
            return "4:3"
        elif abs(ratio - 1.777) < 0.1:
            return "16:9"
        elif abs(ratio - 1.6) < 0.1:
            return "16:10"
        elif abs(ratio - 1.414) < 0.1:
            return "A4竖向"
        else:
            return f"自定义({width:.0f}x{height:.0f})"

    def _pdf_to_images(self, progress_callback=None):
        self.temp_pic_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(self.pdf_path)
        page_count = len(doc)
        img_paths = []
        for i in range(page_count):
            page = doc[i]
            matrix = fitz.Matrix(self.zoom, self.zoom)
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            img_path = self.temp_pic_dir / f"page-{i}.png"
            pix.save(str(img_path))
            img_paths.append(img_path)
            
            # 如果有回调，就通知进度（当前完成第 i+1 页，总共 page_count 页）
            if progress_callback:
                progress_callback(i + 1, page_count)
        
        doc.close()
        return img_paths, page_count

    def _images_to_pptx(self, img_paths):
        """将图片逐页插入指定比例的 PPT 模板"""
        template_map = {
            "4:3": "4ratio3.pptx",
            "16:9": "16ratio9.pptx",
            "16:10": "16ratio10.pptx",
            "A4": "A4.pptx"
        }
        template_file = self.template_dir / template_map[self.target_ratio]
        prs = Presentation(str(template_file))
        blank_layout = prs.slide_layouts[6]
        left, top = Inches(0), Inches(0)
        width, height = prs.slide_width, prs.slide_height

        for img_path in img_paths:
            slide = prs.slides.add_slide(blank_layout)
            slide.shapes.add_picture(str(img_path), left, top, width, height)

        prs.save(str(self.output_path))

    def run(self):
        """执行完整的 PDF → PPTX 转换，返回输出文件路径"""
        img_paths, _ = self._pdf_to_images()
        self._images_to_pptx(img_paths)
        return str(self.output_path)