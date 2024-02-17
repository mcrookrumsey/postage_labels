from flask import Flask, request, send_file, render_template_string
import fitz  # PyMuPDF for PDF processing
from PIL import Image, ImageOps
import io

app = Flask(__name__)

# HTML template for the file upload form with added CSS for styling
UPLOAD_FORM = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Upload PDF</title>
  <style>
    body { font-family: Arial, sans-serif; background-color: #f8f9fa; margin: 40px; }
    .container { max-width: 500px; margin: auto; padding: 20px; background-color: #fff; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,.1); }
    h2 { text-align: center; color: #333; margin-top: 20px; }
    form { display: flex; flex-direction: column; gap: 10px; }
    input[type="file"], input[type="submit"] { border: 1px solid #ccc; display: block; width: 100%; padding: 6px; margin-top: 10px; }
    input[type="submit"] { background-color: #007bff; color: white; border: none; border-radius: 4px; cursor: pointer; }
    input[type="submit"]:hover { background-color: #0056b3; }
    .logo { display: block; margin: auto; margin-bottom: 20px; } /* Center the logo */
  </style>
</head>
<body>
<div class="container">
  <img src="/static/images/logo.png" alt="Logo" class="logo" width="200"> <!-- Adjust the src path and width as needed -->
  <h2>Upload postage label pdf to add hazard label</h2>
  <form method="post" enctype="multipart/form-data" onsubmit="handleSubmit()">
    <input type="file" name="pdf">
    <input type="submit" value="Upload" id="submit-btn">
  </form>
</div>
<script>
  function handleSubmit() {
    const submitBtn = document.getElementById('submit-btn');
    submitBtn.value = 'Processing...'; // Change button text
    submitBtn.disabled = true; // Optional: Disable button to prevent multiple submissions
  }
</script>
</body>
</html>
"""


@app.route('/', methods=['GET'])
def form():
    return render_template_string(UPLOAD_FORM)


@app.route('/', methods=['POST'])
def upload_pdf():
    if 'pdf' not in request.files:
        return 'No file part', 400
    file = request.files['pdf']
    if file.filename == '':
        return 'No selected file', 400
    
    try:
        modified_pdf = process_pdf(file)
        return send_file(modified_pdf, as_attachment=True, download_name='modified_pdf.pdf', mimetype='application/pdf')
    except Exception as e:
        return str(e), 500
    
def combine_images_if_possible(images):
    combined_images = []
    i = 0
    while i < len(images):
        img = images[i]
        if i + 1 < len(images):
            # Create a new blank image with the same width and double the height
            combined_img = Image.new("RGB", (img.width, img.height * 2), "white")
            combined_img.paste(img, (0, 0))  # Paste the first image on top
            combined_img.paste(images[i + 1], (0, img.height))  # Paste the second image on bottom
            combined_images.append(combined_img)
            i += 2  # Move to the next pair of images
        else:
            combined_images.append(img)  # If an odd number of images, add the last image as is
            break
    return combined_images

def process_pdf(pdf_file):
    # Load the predetermined sticker
    sticker_path = 'static/images/sticker.jpg'
    sticker_image = Image.open(sticker_path)
    resized_sticker = sticker_image.resize((int(sticker_image.width * 2.55), int(sticker_image.height * 2.55)), Image.Resampling.LANCZOS)

    output = io.BytesIO()
    writer = fitz.open()

    doc = fitz.open(stream=pdf_file.read(), filetype="pdf")
    for page_num in range(len(doc)):
        page_img = convert_pdf_page_to_image(doc, page_num)
        
        # Calculate the new height for the cropped area (top half)
        new_height = page_img.height // 2
        
        # Crop the top half of the page
        top_half_img = page_img.crop((0, 0, page_img.width, new_height))
        
        # Create a new blank image with the same dimensions as the original page
        blank_img = Image.new("RGB", (page_img.width, page_img.height), "white")
        
        # Paste the cropped top half onto the blank image
        blank_img.paste(top_half_img, (0, 0))
        
        # Paste the sticker onto the composite image
        # Note: Adjust x, y for sticker placement if necessary
        x, y = 1275, 55  # These coordinates might need adjustment
        blank_img.paste(resized_sticker, (x, y), resized_sticker.convert('RGBA'))

        # Convert the PIL Image back to a fitz Pixmap and insert into the new PDF
        img_bytes = io.BytesIO()
        blank_img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        pix = fitz.Pixmap(img_bytes)
        new_page = writer.new_page(width=pix.width, height=pix.height)
        new_page.insert_image(new_page.rect, pixmap=pix)
    
    writer.save(output)
    writer.close()
    
    output.seek(0)
    return output



def convert_pdf_page_to_image(doc, page_number=0, dpi=300):
    page = doc.load_page(page_number)  # 0-indexed
    zoom = dpi / 72
    mat = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=mat)
    img_bytes = pix.tobytes("ppm")
    img = Image.open(io.BytesIO(img_bytes))
    return img

if __name__ == '__main__':
    app.run(debug=True)
