# Nguồn của bản Altair rig4

- Bộ hình tách lớp được tạo bằng công cụ imagegen tích hợp từ hình Altair đã có của dự án; nhân vật gốc thuộc Re:CREATORS. Prompt và bản atlas được lưu trong gói kết quả. Không sử dụng model Cubism hoặc SDK Live2D.
- Bộ dựng khung xương, IK, tóc lò xo, vùng chạm và đồng bộ miệng là mã của bản cập nhật, không cần thư viện render tải ngoài.
- Vosk 0.3.45 và model nhỏ Nhật 0.22: https://github.com/alphacep/vosk-api ; https://alphacephei.com/vosk/models . Giữ manifest nguồn/SHA-256 tại .altair-runtime/asr-ja/manifest.json và license/README của các gói.
- Kokoro-82M jf_alpha, bản ONNX INT8: https://huggingface.co/hexgrad/Kokoro-82M ; https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX . Đây là giọng nữ Nhật thay thế, không phải bản sao giọng diễn viên Altair. MODEL_CARD và manifest nằm trong .altair-runtime/tts-ja.
- Misaki: https://github.com/hexgrad/misaki ; pyopenjtalk-plus: https://pypi.org/project/pyopenjtalk-plus/ . Giữ nguyên license trong runtime, cùng bảng phát âm và từ điển. Thư viện Python chỉ được đưa vào tiến trình đọc giọng ngắn hạn.
- Nguồn model suy luận và các thông báo giấy phép trước đó không thay đổi. Không đổi tên nguồn gốc trọng số thành mô hình tự huấn luyện.
