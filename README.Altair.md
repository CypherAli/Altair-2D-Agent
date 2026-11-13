# Altair — nhân vật 2D có khớp, nghe và nói tiếng Nhật

Bản 2026.11.04-rig4. Chạy AltairStudio.bat như trước: mặc định nhân vật trong suốt ở góc dưới màn hình. Chuột phải để mở menu; nhấn đúp mở hội thoại; kéo phần thân hoặc Alt+kéo để di chuyển. Giữ chuột rồi vuốt trên đầu/tóc để tương tác. Chạm gấu váy gọi động tác chỉnh trang.

- 28 trạng thái dùng khung xương 2D tự dựng trên Canvas: cổ/đầu, tóc có lò xo, thân/hông, hai chân, hai tay dùng bài toán hai khớp vai–khuỷu. Đây là cutout 2D, chưa phải mô hình 3D xoay 360 độ hoặc model Live2D Cubism.
- Xoa đầu, ngại ngùng, vuốt tóc, chỉnh gấu váy, vươn vai, chào/vẫy tay, ngủ, cảm ơn, suy nghĩ, chỉ dẫn, cúi chào… có phản ứng riêng. Gọi dậy cử động cả hai tay trong suốt tiếng gọi; nút này là thử động tác, chưa tạo lịch báo thức.
- Các câu tương tác thường dùng là WAV tiếng Nhật có sẵn, phát ngay và hiện phụ đề Việt. Giọng Kokoro jf_alpha là giọng Nhật thay thế, chưa phải giọng gốc nhân vật Altair.
- Chọn “Nghe tiếng Nhật” từ menu hoặc nút mic trong hội thoại. Bấm lần nữa để gửi; tối đa 14 giây ghi âm. Vosk nhỏ tiếng Nhật chạy offline, chỉ nạp khi nhận dạng và thoát sau mỗi câu. Không lưu bản ghi âm. Hệ điều hành/trình duyệt có thể yêu cầu cấp quyền microphone.
- Lời chào và một số lệnh Nhật như こんにちは, 起こして, おやすみ, ありがとう, 手を振って được xử lý tại giao diện, không gọi LLM. Câu hỏi khác đi vào lõi Altair. Khi bật giọng đọc, câu trả lời mở yêu cầu Việt/Nhật trong cùng một lượt suy luận; bản dịch chưa hoàn tất thì giữ phụ đề thay vì đọc sai.
- Chốt RAM hiện có được giữ nguyên. TTS và ASR cùng chia khóa với suy luận, không chạy đồng thời ba model. Khi RAM trống dưới 600 MiB, chưa nạp ASR/TTS động; các câu WAV sẵn vẫn dùng được. Lõi LLM giữ ngưỡng nạp riêng 1.300 MiB và cơ chế tự nhả RAM.
- Đây là bản Windows đã triển khai. Mã Canvas dùng được trong trình duyệt, nhưng chưa có APK Android/overlay hoặc kết quả đo FPS và pin trên Redmi.

Không gọi API model trả phí; tra cứu web vẫn cần mạng. Runtime tiếng Nhật và ASR được cài một lần trong .altair-runtime/tts-ja và .altair-runtime/asr-ja. Phần TTS tái sử dụng ONNX Runtime đã cài trong .altair-runtime/tts/python. Model suy luận, ghi nhớ và lịch sử cũ được giữ lại.

---

# Altair — lõi local có harness và skills

Cập nhật 04/11/2026. Chạy `AltairStudio.bat` trong AI_AGENT. Bản nâng cấp này dùng lại model/runtime đã cài, không tải model mới, không thêm thư viện nặng hoặc gọi API model trả phí.

## Đường xử lý

1. Nhận yêu cầu và chọn một skill phù hợp.
2. Với biểu thức số, đổi đơn vị, kế hoạch thời gian theo mẫu rõ ràng, Sudoku, tên trợ lý, giờ hiện tại và lưu/xem ghi nhớ: dùng công cụ Python có giới hạn, không gọi LLM.
3. Với hỏi đáp mở, đề xuất phương án và ảnh: gọi Gemma một lần, chỉ nạp hướng dẫn của skill đã chọn và ghi nhớ liên quan.
4. Giới hạn câu trả lời mặc định, trả chữ theo luồng, dùng lại hội thoại native khi tiền tố khớp chính xác. Cache tối đa 32 câu trả lời dưới 4.000 ký tự, trong 5 phút, theo toàn bộ nội dung ngữ cảnh; không cache ảnh.

19 skill nằm trong `altair_core/skills/*/SKILL.md`. Chỉ đọc metadata khi khởi tạo danh sách; phần hướng dẫn được đọc khi cần. Các công cụ tính toán nằm trong `toolkit.py`; thêm file SKILL.md không tự tạo khả năng thực thi mới. Không tự tải hoặc chạy mã từ skill trên mạng.

## Thử ngay

- `Tính (125000 * 3 - 50000) / 2`
- `20% của 250000`
- `Đổi 2,5 km sang m`
- `Tôi có 60 phút rảnh. Đi bộ mất 10 phút mỗi chiều. Chơi 45 phút. Có kịp về trong 60 phút không?`
- `Giải sudoku` rồi dán 9 dòng × 9 số; dùng 0/dấu chấm cho ô trống. Hoặc gửi một chuỗi 81 ký tự. `Gợi ý sudoku` chỉ một ô có một ứng viên khi tìm được.
- `Hãy nhớ rằng tôi thích trà không đường.` rồi `Tôi thích uống gì?`
- `Giải thích ngắn vì sao có mưa.` rồi `Nói rõ hơn một chút.`

Công cụ thời gian chỉ xử lý các khoảng thời gian được nêu rõ, cộng các việc và nhân hai với “mỗi chiều”. Nó hỏi lại khi không xác định được ngân sách hoặc số lượt. Đây chưa phải bộ hiểu mọi bài toán bằng lời. Model trả lời mở và vision vẫn có thể sai; cache giữ nguyên chất lượng câu trả lời gốc.

## RAM và tốc độ

- Dùng nguyên `google/gemma-4-E2B-it`, bản LiteRT mobile. Model ở `.altair-runtime/litert/altair.litertlm`, khoảng 2,59 GB trên đĩa. Không fine-tune hoặc đổi nguồn gốc trọng số.
- Mặc định context 2.048 token, tối đa 4 luồng CPU, một lượt suy luận. Đầu ra 96–160 token tùy yêu cầu thường, 320 khi yêu cầu chi tiết; giới hạn cấu hình 384 là trần mặc định. Không chạy vòng tự suy nghĩ/tự chấm nhiều lần.
- Giữ một hội thoại native dưới 1.200 token để dùng tiếp khi khớp. Khi thay skill/ghi nhớ/lịch sử, tạo hội thoại phù hợp mới.
- Khi rảnh: giữ engine tối đa 180 giây nếu RAM trống ít nhất 2 GiB, còn 45 giây khi thấp hơn; kiểm tra mỗi 10 giây. Nếu RAM trống dưới 900 MiB thì nhả engine. Từ chối nạp model mới khi RAM trống dưới 1.300 MiB trên Windows.
- Nút **Tắt AI** nhả engine và cache native. Tính toán, Sudoku, giờ và ghi nhớ vẫn dùng được. Nút **Dừng** hủy sinh; câu trả lời dở không lưu vào lịch sử.
- Các mức RAM là biện pháp giảm áp lực, không phải giới hạn RAM cứng. Vision cần nhiều RAM/thời gian hơn chat. Chưa đo APK trên Redmi; đây là bản Windows.

Lịch sử/ghi nhớ ở `.altair-runtime/history.json` và `notes.json`. Không gửi chúng ra ngoài. Tìm kiếm web đã được nối. Báo thức, Maps, cờ vua và điều khiển Android chưa được nối; Altair phải báo rõ khi chưa thực hiện được. Giao diện/hoạt ảnh nhân vật sẽ phát triển riêng.

## Kiểm tra và khôi phục

`python -m unittest discover -s tests -v`

Trước nâng cấp có bản sao mã trong `.altair-backup-optimization-<thời gian>/` kèm manifest SHA256. Model 7B cũ và model Altair hiện tại đều được giữ nguyên. Chỉ khôi phục mã khi ứng dụng đã đóng; không ghi đè dữ liệu cá nhân trong `.altair-runtime`.

Hướng dẫn kỹ thuật tham khảo: [Agent Skills: progressive disclosure](https://agentskills.io/client-implementation/adding-skills-support), [LiteRT-LM Gemma 4](https://developers.google.com/edge/litert-lm/models/gemma-4). Bản này chưa bật MTP; lợi ích phụ thuộc dạng tác vụ và chưa được đo phù hợp trên máy này.


## Tra cứu có nguồn — 2026.11.04-search1

- `Tìm Google Jev TypeSafe AI confidence`: trả đoạn trích ngắn, liên kết thật và thời điểm đọc, không nạp model.
- Thêm `, tổng hợp` để model local viết bản tổng hợp tiếng Việt kèm [1], [2]. Việc kiểm tra số trích dẫn/số liệu chỉ là chốt kỹ thuật cơ bản, chưa xác minh hết ý nghĩa của bản tổng hợp.
- Chọn Tự động tra cứu / Tra cứu web / Không tra cứu trong ô chat. Một số câu hỏi dữ liệu hiện tại tự kích hoạt web; yêu cầu ghi nhớ, câu hỏi cá nhân và ảnh vẫn xử lý riêng. Chỉ câu truy vấn hiện tại được gửi tới nguồn web, không gửi toàn bộ lịch sử/ghi nhớ.
- Google được thử trước, nhưng HTML có thể yêu cầu JavaScript hoặc CAPTCHA. Trong mạng thử hiện tại Google chặn cả WebView2 bằng CAPTCHA. Bản chạy thật không mở thêm browser ẩn, không vượt CAPTCHA. Khi Google không dùng được, Altair ghi rõ nguồn thực dùng: tài liệu chính thức đã định tuyến, Wikipedia cho kiến thức ổn định, hoặc Bing RSS. Có liên kết Mở tìm kiếm Google để tra cứu trực tiếp.
- `altair_core/search_sources.json` chỉ chứa tên/URL nguồn chính thức đã kiểm tra, không chứa đáp án. Các trang vẫn được tải thật. Có thể đọc URL công khai được người dùng chỉ định. Nguồn không phù hợp hoặc không đọc được thì báo rõ; không giả vờ đã search thành công.
- Cache 16 lượt tìm kiếm trong 5 phút. Tối đa 2 lượt đọc trang đồng thời; thường 350 KB/trang, tài liệu Android tối đa 1,25 MB. Chỉ lấy nội dung văn bản, không chạy script trang web. Không cần key, tài khoản hoặc gói trả phí. Các nguồn công khai vẫn có thể chặn hoặc thay đổi định dạng.
- Tra cứu nhanh trong bộ thử khoảng 0,4–2,8 giây; tổng hợp mẫu Jev khoảng 7–9 giây. RSS lõi tra cứu không model khoảng 35 MiB; tổng hợp có model khoảng 1,24 GiB, chưa tính WebView2. Không phải cam kết cho mọi câu hỏi/mạng hoặc điện thoại.

## Quyết định và độ chắc chắn

Bổ sung `order-reasoning` và `constraint-choice`: so sánh thứ tự từ các quan hệ rõ ràng, và kiểm tra từng phương án A/B với ngân sách/thời gian. Không cộng các phương án thay thế; không tự chọn giữa nhiều phương án cùng đạt khi chưa có ưu tiên. Các dạng ngoài mẫu vẫn có thể cần model hoặc dữ kiện bổ sung.

API trả `metrics.judgment` với trạng thái kết quả công cụ, thiếu dữ kiện, trích nguồn, tổng hợp model hoặc cần kiểm tra. `probability_correct` là null và `calibrated` là false: chưa có bộ dữ liệu đủ để hiệu chỉnh xác suất. Không gắn số 95% tùy ý. Đây không phải Jev chạy local; không gọi API Jev.

57 unit test và 13 kiểm tra HTTP với nguồn/model thật đã qua ở lần nâng cấp. Bộ chẩn đoán suy luận 6 câu đạt 6/6 sau sửa, trước đó có 2 câu sai nội dung và 1 câu sai định dạng. Đây là bộ phát triển nhỏ, không phải Intelligence Index, IQ hoặc bằng chứng model đạt 100% trên dữ liệu mới.

Tham khảo: [TypeSafe Confidence](https://docs.typesafe.ai/confidence), [Artificial Analysis methodology](https://artificialanalysis.ai/methodology/intelligence-benchmarking), [Google Custom Search API](https://developers.google.com/custom-search/v1/overview). Không cấu hình dịch vụ trả phí; API Google Custom Search hiện đóng với khách hàng mới theo tài liệu chính thức.


## Đánh giá mở rộng — 2026.11.04-eval4

Đã dùng 120 tình huống tự soạn về sử dụng hằng ngày: 60 phát triển, 40 giữ lại ban đầu và 20 câu mới sau vòng sửa. Không phải benchmark độc lập, IQ hay Intelligence Index. Các tập được khóa hash trước lượt chạy; khi đã dùng để sửa thì chỉ gọi kết quả chạy lại là hồi quy.

Đã sửa tính hóa đơn theo số lượng, giờ rời nhà có dự phòng, việc song song, tên nhiều từ/dấu phẩy, kiểm tra đủ thời gian và tiền, cộng phí giao hàng, nhớ ngữ cảnh câu nối tiếp và phân biệt trạng thái chức năng chưa nối. Có skill logic ngắn cho điều kiện/phủ định. Tổng 18 skills, không thêm framework hoặc model.

Nguồn: tìm đúng tiêu đề/chuyển hướng trước, có đường đọc tên tiếng Anh, giữ chữ viết tắt trong tên tác giả, ưu tiên đoạn định nghĩa và số liệu, kiểm tra mã hàng có khớp. Câu hỏi kiến thức có thể được model hiện tại trả lời ngắn tối đa 64 token; tổng hợp rõ ràng tối đa 128 token, một lượt gọi. Thêm “tìm nhanh”/“chỉ lấy nguồn” hoặc tắt AI để chỉ trích nguồn mà không nạp model. Giữ đủ đoạn bằng chứng cho model; loại một số tên riêng/số liệu mới không có trong bằng chứng. Đây vẫn chưa phải kiểm chứng ngữ nghĩa đầy đủ.

Đã đo đầy đủ trên bản trung gian v3: bộ phát triển 58/60, bộ 40 chạy lại 36/40, 20 câu mới 14/20 sau rà soát nghĩa và nguồn. Phần tính toán/logic trong bộ này tốt hơn tìm kiếm: các chủ đề mới vẫn có thể lấy nhầm đoạn, thiếu bằng chứng hoặc có lỗi tổng hợp. Không gọi tổng điểm này là thông minh 90/100. Báo cáo chi tiết tách câu đã học, câu mới và từ chối khi không đủ dữ kiện.

Đo v3 trên Windows: công cụ dưới 20 ms ở mẫu thử, trả lời local ngắn thường khoảng 1–5 giây, có nguồn thường khoảng 4–8 giây; đỉnh RSS khoảng 1,3 GiB, chưa tính WebView2. Bản v4 đã qua 66 unit test và 9 HTTP test nhẹ, gồm nguồn thật. Lượt hồi quy v4 có lúc máy chỉ còn khoảng 0,5 GiB RAM trống; model được chốt bảo vệ từ chối nạp nên không dùng lượt đó làm điểm suy luận hoặc cam kết tốc độ model.

Giữ nguyên chốt Windows: chưa nạp model nếu RAM trống dưới 1.300 MiB; không bỏ chốt để lấy điểm. Tính toán/tra cứu nhanh vẫn dùng được. Chưa đo APK trên Redmi. Không gọi API model trả phí, không thay trọng số, không gửi toàn bộ ghi nhớ/lịch sử ra web. Google trên mạng thử vẫn có CAPTCHA và nguồn thực dùng được ghi rõ.


## Hiểu ý và bối cảnh — 2026.11.04-context1

Bộ nhớ làm việc theo tối đa 4 chủ đề, 6 lựa chọn mỗi chủ đề, tối đa 12.000 byte JSON trên đĩa; phần chèn vào prompt tối đa 1.100 byte. Chỉ giữ một ít dữ kiện người dùng, không thêm model/embedding/vector database. Model cũ, context và chốt RAM giữ nguyên. Câu sửa rõ thay giá trị cũ; khi mơ hồ thì hỏi lại. Câu hỏi mở vẫn dùng một lượt model hiện có nên có thể hiểu sai hoặc đưa gợi ý chung.

Ví dụ: “Tôi có 100k muốn ăn tối” → “A 80k, B 95k” → “Tính cả ship” → “Ship A 0k, ship B 20k” → “Chọn quán nào vừa túi?”. Có thể nói “Không phải 100k mà 120k”, “Còn B?”, “Nó tổng bao nhiêu?”, chuyển chủ đề rồi “Quay lại ăn tối”. Không đủ dữ kiện thì hỏi lại, không mặc định phí bằng không. Có thể sửa thời gian vừa nói bằng “Nhầm, 45p thôi”. Đây là các mẫu hỗ trợ, chưa phải hiểu mọi câu nói tắt.

Giá trị hiện tại lưu ở `.altair-runtime/conversation.json`, tách khỏi ghi nhớ lâu dài `notes.json`. Lịch sử vẫn 6 lượt; bộ nhớ làm việc có thể giữ dữ kiện cũ hơn. Mở lại ứng dụng dùng dữ kiện đã lưu. Nút Phiên mới hoặc câu “Quên hết bối cảnh” xóa bối cảnh của phiên, không xóa ghi nhớ riêng. Dữ kiện nhập dở/câu trả lời bị hủy không được ghi nhận. Nếu vượt 4 chủ đề thì bỏ chủ đề ít dùng; không giả vờ nhớ phần đã bỏ. Truy vấn nối tiếp web dùng chủ đề công khai, không tự ghép ngân sách/ghi nhớ cá nhân vào truy vấn.

Kiểm tra: 30 hội thoại tự soạn, 125 lượt qua runtime với AI tắt; sau sửa đạt 125/125 kiểm tra trong bộ hồi quy. Bộ giữ lại ban đầu có một lỗi sửa nhầm trường, đã dùng để sửa nên kết quả chạy lại không phải kiểm tra độc lập. 94 unit test và 10 kiểm tra HTTP qua localhost đạt. Thêm 6 hội thoại/21 lượt với model thật: giữ đúng các giá trị đã sửa nhưng một số câu hỏi mở vẫn hỏi thêm hoặc trả lời chung. Không quy đổi thành IQ/điểm thông minh.

Trong lượt cuối trên Windows, phản hồi dùng quy tắc thường vài ms; 5 câu mở dùng model khoảng 3,5–6,3 giây, lượt đầu trước đó có câu mất 15,5 giây. Tốc độ phụ thuộc RAM/cache/CPU, chưa phải số đo trên điện thoại. Không tải thêm trọng số, không API model trả phí, không thêm dependency production.


## Nhân vật 2D và xưng hô — 2026.11.04-character1

Altair xưng em, gọi người dùng là chủ nhân trong hướng dẫn model và câu trả lời dựng sẵn. Câu gốc/lời trích trong ghi nhớ và nguồn web được giữ nguyên; không thay đại từ bằng cách sửa mọi dữ liệu đầu vào.

Giao diện có nhân vật Altair lấy cảm hứng từ Re:CREATORS, dùng một atlas PNG khoảng 3 MB, 16 tư thế và 12 trạng thái: nghỉ chờ/chớp mắt, vẫy tay, nói, suy nghĩ, tìm nguồn, chú ý, hỏi lại, vui/gật đầu, ngạc nhiên, gọi dậy, nghỉ nhắm mắt và lỗi. Mở “Biểu cảm và chuyển động” để thử thêm. Hoạt ảnh hiện tại ghép khung hình và chuyển động nhẹ; chưa phải rig Live2D hay khẩu hình khớp từng âm.

Nút Gọi dậy chỉ xem thử động tác, chưa đặt báo thức. “Chú ý” cũng là tư thế, chưa mở mic. Khi trả lời, nhân vật tự chuyển sang suy nghĩ/miệng nói; khi thiếu dữ kiện thì hỏi lại. “Tra cứu web” chuyển sang trạng thái tìm nguồn trong lúc chờ. Vẫn dùng một model, không API tạo ảnh hoặc gọi model thêm khi phát hoạt ảnh.

Hoạt ảnh dừng khi trang bị ẩn; có Giảm chuyển động và Dừng động tác/giọng. Giọng đọc mặc định tắt. Chỉ dùng giọng tiếng Việt được trình duyệt báo là localService khi có sẵn trên máy, không chọn giọng cloud. Máy thử chưa có giọng Việt offline nên dùng khẩu hình mô phỏng theo chữ, không phát tiếng; không kèm model giọng nói hay giọng diễn viên anime.

Đã qua 98 unit test, 8 kiểm tra controller JavaScript về đổi khung/dừng/timer/giọng local, kiểm tra giao diện 1280px và 390px không tràn ngang và thử hai câu mở bằng model thật với xưng hô chủ nhân. Bố cục 390px là mô phỏng trong trình duyệt Windows, chưa phải kiểm tra APK hoặc đo pin/RAM trên Redmi. Một atlas giải mã RGBA khoảng 6 MiB; không phải tổng RAM ứng dụng. WebView2 và model vẫn có chi phí bộ nhớ riêng.

Chạy kiểm tra hoạt ảnh: `node tests/test_character.cjs`. Tạo hình được dựng bằng công cụ imagegen từ ảnh tham chiếu người dùng cung cấp, chưa phải model Live2D chính thức của phim.


## Toàn thân, chuyển động mềm và giọng Việt — 2026.11.04-voice2

Trong khung nhân vật, kéo lên/đẩy cuộn chuột để xem váy, chân và giày; nút Toàn thân đưa toàn bộ nhân vật vừa khung. Có Chân dung, Về đầu và thanh thu phóng. Khi chọn khung bằng bàn phím, dùng mũi tên lên/xuống, Home/End. Camera có giới hạn để không kéo nhân vật ra ngoài vô tận.

Giữ atlas chân dung cũ 16 tư thế, thêm atlas toàn thân 8 tư thế: tổng 24 tư thế, 20 trạng thái/động tác kết hợp. Thêm chào quân phục, chỉ dẫn, cảm ơn, cúi chào, đồng ý, cân nhắc, động viên và đọc kỹ. Tư thế chuyển mờ nhẹ thay vì đổi khung đột ngột. Khi nói, phần thân giữ ổn định và vùng miệng đổi riêng. Đây vẫn là hoạt ảnh sprite/CSS, chưa phải rig Live2D đầy đủ.

Giọng nữ Việt VAIS1000 dùng Piper 1.8.0 + ONNX Runtime CPU, 2 luồng. Trọng số khoảng 63 MB (60,3 MiB), phần thư viện riêng khoảng 148 MiB trên đĩa. Không tải khi đọc, không API, không GPU, không clone giọng diễn viên. Worker mạng Python bị khóa, chạy mỗi lượt rồi thoát; hai mẫu thử đạt đỉnh RSS lấy mẫu khoảng 160–165 MiB. Không phải số đo tổng RAM ứng dụng. Giữ một khóa tính toán chung với model để không nạp/suy luận đồng thời; từ chối tạo giọng mới nếu RAM trống dưới 600 MiB. Cache âm thanh trong RAM tối đa 2 mục/4 MiB/120 giây.

Miệng theo mức âm thanh đang phát qua Web Audio (tối đa khoảng 30 lần cập nhật/giây), khép trong im lặng và khi dừng. Đây là đồng bộ độ mở theo âm lượng, chưa có hình miệng chính xác theo từng âm vị. Nhấn Nói/Gọi dậy để nghe ngay các câu mẫu có sẵn; Đọc câu trả lời bật giọng cho nội dung mới, tối đa 500 ký tự mỗi lượt. Tắt tùy chọn này để dùng chữ. Nút Dừng động tác/giọng, nút Dừng câu trả lời hoặc ẩn trang đều dừng tiếng/khẩu hình. Gọi dậy vẫn là câu gọi và động tác mẫu, chưa tạo báo thức nền.

Đã kiểm tra 107 unit test, 7 kiểm tra camera/âm thanh bằng JavaScript, 10 kiểm tra HTTP gồm âm thanh thật, cache, hủy worker và hỏi tiếp sau hủy. Đã tạo WAV khi mạng Python bị chặn; trên mẫu HTTP, khoảng 3,3 giây tạo 2,2 giây tiếng và cache khoảng 24 ms. Hai mẫu độc lập trước đó khoảng 4,1–4,8 giây tạo gần 3,9 giây tiếng. Chưa đo APK hay pin trên Redmi. Có sửa câu hỏi hôm nay thứ mấy sang công cụ đồng hồ máy và tránh lỗi Unicode của strftime trên Windows.

Giọng đã cài trong `.altair-runtime/tts`. Nếu cần cài lại, chạy `python setup_altair_voice.py` một lần khi có mạng; khi dùng thì không cần mạng. Nguồn và giấy phép được ghi trong NOTICE.Altair-voice.md và model card gốc.

## Khớp mềm, tóc dài và giao diện tương tác — 2026.11.13-ui1

- Tóc: lọn tóc giữ đúng tỉ lệ gốc của atlas (bản trước kéo dọc khoảng 1,9 lần nên thành vệt). Nay vẽ hai lớp, lọn trước che gốc lọn sau, nên dài tới gần gấu váy mà không méo; mỗi lớp uốn theo góc đầu và có lò xo riêng nên có quán tính khi cúi, nghiêng hoặc khi chủ nhân vuốt tóc.
- Vai: ống tay cắt sẵn với mép trên/dưới mờ dần, đầu vai tròn xoay theo tay, cầu vai vẽ đè lên trên. Tay đi ra từ dưới cầu vai thay vì lộ góc vuông khi giơ lên.
- Khuỷu: găng tay vẽ dưới ống tay, mép ống tay mờ dần vào găng. Đã bỏ miếng che tròn ở khuỷu vì nó tạo cảm giác khớp búp bê.
- Bóng tiếp xúc chỉ tô lên phần đã vẽ (source-atop): dưới cằm, dưới tóc trên vai, nách, eo, dưới cầu vai — các mảng khít vào nhau thay vì nổi như giấy cắt rời.
- Chuyển động: pha trộn theo nhóm (hông dẫn, tay theo sau, đầu về cuối), khuỷu chọn nghiệm phía ngoài có trễ chống lật, tay chạm mặt tính theo toạ độ đầu, 60 khung/giây khi có động tác (30 khi chờ, 10 khi giảm chuyển động).
- Giao diện: khung nhân vật có viền sáng và vignette, hàng gợi ý chạm tự ẩn sau lần chạm đầu, dock 6 tương tác nhanh, danh sách biểu cảm chia nhóm, khung mặc định vừa toàn thân. Cửa sổ nhân vật trên màn hình có dock Nói/Mic/Vẫy/Menu luôn hiện mờ; đã sửa các quy tắc CSS có dấu "+" thừa từng bị trình duyệt bỏ qua khiến WebView2 không vẽ lại lớp phủ.
- Kiểm tra: 8 test rig, 7 test character, 4 test greeting, 3 test microphone đều qua; đã xem ảnh chụp phóng 4 lần phần vai/khuỷu và tóc ở các tư thế nghỉ, vẫy tay, ngại ngùng, vươn vai. Chưa chạy trong cửa sổ WebView2 thật và chưa đo FPS trên máy yếu.
- Giới hạn còn lại: đây vẫn là cutout 2D (không xoay 360 độ), chân/hông chưa có khớp gối, và tà tóc là hai lớp lọn chứ chưa phải một lưới uốn liền. Miệng vẫn mở theo âm lượng, chưa theo từng âm vị.
- Tham khảo kỹ thuật: [Godot cutout animation](https://docs.godotengine.org/en/stable/tutorials/animation/cutout_animation.html), [12 nguyên tắc hoạt ảnh](https://helpcentre.toonboom.com/hc/en-ca/articles/57087608774931-About-the-12-Principles-of-Animation), [nhịp và hướng chuyển động trong Live2D](https://live2dnote.com/05%20Motion%20&%20Animation/Clean%20Communication%20of%20Motion%20Intent%20in%20Live2D).

## Cổ, tóc và câu hỏi ngày giờ — 2026.11.13-ui2

- Hạ đầu xuống 4 đơn vị (NECK_Y 122 → 126) và dời miếng che cổ xuống theo, nên cổ không còn cao lêu nghêu; cằm vẫn nằm trên cổ áo chứ không bị cổ áo nuốt.
- Kéo hai lọn tóc vào gần đầu (x 106/194 thay vì 96/204) và neo cao hơn (y 100), nên tóc dính vào đầu thay vì hai búi tách rời hai bên.
- Sửa lỗi thật của câu hỏi ngày giờ: bộ định tuyến so khớp **nguyên câu** nên chỉ đúng "hôm nay là thứ mấy" và "hôm nay thứ mấy" mới vào công cụ đồng hồ; "hôm nay thứ mấy ạ?", "hôm nay là thứ mấy nhỉ", "cho mình hỏi hôm nay là thứ mấy", "mấy giờ rồi em" bị đẩy sang tìm web/model (và báo lỗi khi AI tắt). Nay dùng mẫu câu (`clock_question`), nhận cả câu có đuôi lịch sự, và trả lời tại máy trong vài ms, không gọi model.
- Kiểm tra chức năng thật qua HTTP (cổng 8124, chạy `altair_native.py --headless`): 3 cách hỏi ngày giờ đều trả lời đúng thứ/ngày; tính toán 162.500; đổi 2,5 km = 2500 m; hỏi tên; `/api/status`, `/api/tts/status`, `/api/history` trả 200; một câu mở qua `/api/ask_stream` mất 18,4 giây cho 41 token (5,77 token/giây, có nạp model); tìm web 3,3 giây và trả 1 nguồn; Sudoku trả lời thiếu đề.
- 125 unit test Python và 22 kiểm tra JavaScript đều qua. Chưa kiểm tra: micro/ASR (cần quyền micro), tạo giọng TTS thật (cần nạp worker và đủ RAM), cửa sổ pet native, và ghi ghi nhớ (để tránh sửa dữ liệu cá nhân của chủ nhân).

## Giao diện một màn hình — 2026.11.13-ui3

- Trước đây cả trang là một cột dài (cao ~1650px trên cửa sổ 860px): header cuộn mất, ô nhập câu hỏi nằm dưới đáy màn hình, và mở app là tự nhảy xuống cuối. Nay `body.app-shell` khoá chiều cao màn hình, khung chat tự cuộn bên trong, ô nhập luôn nằm trong tầm tay; trang không còn cuộn.
- Trạng thái runtime (model, ngữ cảnh, token/giây) chuyển từ khối `details` ở đáy trang lên một viên thuốc gọn giữa header, chuột vào xem đầy đủ; header gọn hơn ~30px.
- Chân dung Altair co theo chiều cao cửa sổ (42vh, tối đa 410px) nên toàn thân vẫn vừa khung mà không cần cuộn cột trái.
- Thêm màn hình khởi đầu khi chưa có hội thoại: một thẻ gợi ý kèm 3 nút bấm sẵn ("Hôm nay thứ mấy?", "Tính 125000 × 3", "Đổi 2,5 km sang m") — bấm là gửi luôn; cả 3 đều trả lời ngay trên máy, không chờ model.
- Bong bóng của chủ nhân co đúng nội dung và dính phải; thân bài của Altair giới hạn 74ch cho dễ đọc; câu trả lời đang chạy chữ tự cuộn xuống nếu đang ở gần cuối.
- Gợi ý chạm trên khung nhân vật xuống dòng thay vì bị cắt ("Xoa đầu · Vuốt tóc · Chạm váy · Đúp: chat"), và tự ẩn sau 7 giây như trước.
- Ghi chú nhỏ: `chat.html` và `pet.html` không dùng class `app-shell` nên giữ nguyên bố cục cũ. Trên màn hình hẹp (≤900px) app trở lại bố cục một cột cuộn dọc như trước.
- Kiểm tra: `app.js` parse OK; 22 kiểm tra JavaScript qua (rig, character, greeting); trang chạy trên Chromium thật (cửa sổ 1280×860 và 390×844, không tràn ngang, `scrollHeight == innerHeight` ở desktop); bấm thử nút gợi ý thấy điền câu và gửi đúng một lần. Chưa kiểm tra: giao diện trong WebView2 native và cửa sổ pet.
