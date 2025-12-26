import fitz
import sys

doc = fitz.open(r'Informe Técnico Definitivo sobre la Generación de Alfa en Polymarket.pdf')
text = ''
for page in doc:
    text += page.get_text()

# Write to file to avoid encoding issues
with open('pdf_content.txt', 'w', encoding='utf-8') as f:
    f.write(text)

print("PDF content extracted to pdf_content.txt")
print(f"Total characters: {len(text)}")
