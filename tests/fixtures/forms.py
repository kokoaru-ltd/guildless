"""Local fixture pages covering every contact-form shape worth handling.

Deterministic and offline. Real sites are the thing being prepared for, not the
thing being tested against, because a test that depends on someone else's
website fails for reasons that have nothing to do with this code.
"""

from __future__ import annotations


BASE_FORM = """
<h1>お問い合わせ</h1>
<p>サービスに関するご相談を受け付けております。</p>
<form id="contact" onsubmit="return false;">
  <label for="company">会社名</label><input id="company" name="company" required>
  <label for="name">お名前</label><input id="name" name="your_name" required>
  <label for="email">メールアドレス</label><input id="email" name="email" type="email" required>
  <label for="tel">電話番号</label><input id="tel" name="tel">
  <label for="subject">件名</label><input id="subject" name="subject">
  <label for="body">お問い合わせ内容</label><textarea id="body" name="message" required></textarea>
  <button type="button" id="send">送信する</button>
</form>
<div id="result"></div>
"""

#: Ordinary form that confirms acceptance in one step.
NORMAL_SUCCESS = BASE_FORM + """
<script>
document.getElementById('send').onclick = () => {
  document.getElementById('contact').style.display = 'none';
  document.getElementById('result').innerText = '送信しました。ありがとうございました。';
};
</script>
"""

#: Two-step form: confirm, then send.
CONFIRMATION_PAGE = BASE_FORM.replace(
    '<button type="button" id="send">送信する</button>',
    '<button type="button" id="confirm">確認画面へ</button>'
) + """
<script>
document.getElementById('confirm').onclick = () => {
  document.getElementById('contact').style.display = 'none';
  document.getElementById('result').innerHTML =
    '<p>この内容でよろしいですか</p><button type="button" id="send">送信する</button>';
  document.getElementById('send').onclick = () => {
    document.getElementById('result').innerText = '受け付けました。受付番号: AB-99120';
  };
};
</script>
"""

#: Fields injected after load, invisible to a raw HTTP fetch.
JS_INJECTED = """
<h1>お問い合わせ</h1>
<form id="contact" onsubmit="return false;"></form>
<div id="result"></div>
<script>
const f = document.getElementById('contact');
f.innerHTML = `
  <label for="c">会社名</label><input id="c" name="company" required>
  <label for="n">お名前</label><input id="n" name="your_name" required>
  <label for="e">メールアドレス</label><input id="e" name="email" type="email" required>
  <label for="m">お問い合わせ内容</label><textarea id="m" name="message" required></textarea>
  <button type="button" id="send">送信する</button>`;
document.getElementById('send').onclick = () => {
  document.getElementById('result').innerText = 'お問い合わせありがとうございます。';
};
</script>
"""

#: A required field whose purpose cannot be established.
UNKNOWN_REQUIRED_FIELD = """
<h1>お問い合わせ</h1>
<form id="contact" onsubmit="return false;">
  <label for="email">メールアドレス</label><input id="email" name="email" type="email" required>
  <label for="body">お問い合わせ内容</label><textarea id="body" name="message" required></textarea>
  <label for="zz">Q7-B</label><input id="zz" name="q7b" required>
  <button type="button" id="send">送信する</button>
</form>
"""

CAPTCHA_FORM = BASE_FORM + """
<div class="g-recaptcha" data-sitekey="6Ldxxxx"></div>
<script src="https://www.google.com/recaptcha/api.js"></script>
"""

#: Hidden field a human never sees. Filling it identifies the sender as a bot.
HONEYPOT_FORM = """
<h1>お問い合わせ</h1>
<form id="contact" onsubmit="return false;">
  <label for="company">会社名</label><input id="company" name="company" required>
  <label for="email">メールアドレス</label><input id="email" name="email" type="email" required>
  <label for="body">お問い合わせ内容</label><textarea id="body" name="message" required></textarea>
  <div style="position:absolute;left:-9999px;">
    <label for="url2">Website</label><input id="url2" name="url_confirm">
  </div>
  <button type="button" id="send">送信する</button>
</form>
<div id="result"></div>
<script>
document.getElementById('send').onclick = () => {
  const trap = document.querySelector('[name=url_confirm]').value;
  document.getElementById('result').innerText =
    trap ? 'エラーが発生しました' : '送信しました。ありがとうございました。';
};
</script>
"""

#: Returns a page, but it is a validation complaint rather than acceptance.
AMBIGUOUS_SUCCESS = BASE_FORM + """
<script>
document.getElementById('send').onclick = () => {
  document.getElementById('result').innerText =
    'ご入力ありがとうございます。必須項目が未入力です。必須項目をご確認ください。';
};
</script>
"""

#: Navigates and says nothing either way.
NO_CONFIRMATION = BASE_FORM + """
<script>
document.getElementById('send').onclick = () => {
  document.getElementById('contact').style.display = 'none';
  document.getElementById('result').innerText = 'ホームへ戻る';
};
</script>
"""

SALES_PROHIBITED_PAGE = """
<h1>お問い合わせ</h1>
<p>営業目的でのご連絡はお断りしております。</p>
""" + BASE_FORM

RECRUITMENT_ONLY = """
<h1>採用に関するお問い合わせ</h1>
<p>こちらは採用応募専用のフォームです。</p>
""" + BASE_FORM


FIXTURES = {
    "normal_success": NORMAL_SUCCESS,
    "confirmation_page": CONFIRMATION_PAGE,
    "js_injected": JS_INJECTED,
    "unknown_required_field": UNKNOWN_REQUIRED_FIELD,
    "captcha": CAPTCHA_FORM,
    "honeypot": HONEYPOT_FORM,
    "ambiguous_success": AMBIGUOUS_SUCCESS,
    "no_confirmation": NO_CONFIRMATION,
    "sales_prohibited": SALES_PROHIBITED_PAGE,
    "recruitment_only": RECRUITMENT_ONLY,
}
