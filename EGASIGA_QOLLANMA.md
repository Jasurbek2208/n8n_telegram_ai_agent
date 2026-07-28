# 📱 Foydalanish qo'llanmasi

> Bu qo'llanma tizim **egasi** uchun. Kompyuter, terminal yoki dasturlash bilishingiz shart emas.
> Hamma ish telefoningizdagi **Telegram** orqali bajariladi.

---

## Bu tizim nima qiladi?

Siz Telegram profillaringizni tizimga qo'shasiz. Shundan keyin o'sha profillarga
kelgan shaxsiy xabarlarga **sun'iy intellekt avtomatik javob beradi** — siz
telefoningizga qaramasangiz ham.

Tizim serverda 24/7 ishlaydi. Elektr o'chsa yoki server qayta yuklansa —
o'zi avtomatik yoqiladi.

---

## 1. Boshqaruv boti

Telegramda **@n8n_agent_for_telegram_bot** ni qidiring va **/start** yozing.

Shu bot — sizning boshqaruv pultingiz. Doim shu yerdan ishlaysiz.

Ekranda quyidagi tugmalar chiqadi:

```
🤖 Userbot boshqaruvi

Jami profillar: 1
✅ Ishlayapti: 1

➕ Yangi profil qo'shish
📋 Profillar ro'yxati
```

---

## 2. Yangi profil qo'shish

**«➕ Yangi profil qo'shish»** tugmasini bosing. Bot ketma-ket savol beradi:

### 1-savol: Telefon raqam

Qo'shmoqchi bo'lgan Telegram akkauntning raqamini yozing:

```
+998901234567
```

### 2-savol: n8n havolasi

Bu profil xabarlarni qayerga yuborishini bildiradi.

Odatda **«✅ Odatdagi havolani ishlatish»** tugmasini bossangiz kifoya.

### 3-qadam: Tekshirish

Bot yozganlaringizni ko'rsatadi. To'g'ri bo'lsa **«✅ Ha, davom etish»** ni bosing.

### 4-qadam: Telegram kodi

Telegram o'sha raqamga 5 xonali kod yuboradi. Uni topib, botga yozing.

> ### ⚠️ ENG MUHIM QOIDA
>
> Kodni **oddiy holda yozmang**. Agar `12345` deb yozsangiz —
> Telegram xavfsizlik uchun bu kodni **bekor qiladi** va ishlamaydi.
>
> Har bir raqam orasiga **chiziqcha** qo'ying:
>
> ### ✅ To'g'ri: `1-2-3-4-5`
> ### ❌ Noto'g'ri: `12345`
>
> Bu Telegramning o'z qoidasi, biz o'zgartira olmaymiz.

### 5-qadam: Parol (agar bo'lsa)

Agar o'sha akkauntda **ikki bosqichli himoya** yoqilgan bo'lsa, bot parol so'raydi.
Parolni yozing.

> 🔒 Xavfsizlik: yozgan parolingizni bot **darhol o'chirib tashlaydi** va
> uni hech qayerda saqlamaydi. Faqat kirish uchun bir marta ishlatiladi.

### Tayyor ✅

```
✅ acc2 profili muvaffaqiyatli ulandi!
```

Shu paytdan boshlab profil ishlay boshlaydi.

---

## 3. Profillarni ko'rish va boshqarish

**«📋 Profillar ro'yxati»** tugmasi barcha profillarni ko'rsatadi:

| Belgi | Ma'nosi | Nima qilish kerak |
|-------|---------|-------------------|
| ✅ | Ishlayapti | Hech nima — hammasi joyida |
| ⚠️ | Qayta kirish kerak | «🔄 Qayta kirish» tugmasini bosing |
| ⏸ | To'xtatilgan | Kerak bo'lsa «▶️ Yoqish» |
| ❌ | Xatolik | Dasturchiga murojaat qiling |

Profil ustiga bossangiz uning sahifasi ochiladi:

- **⏸ To'xtatish** — profil vaqtincha javob bermaydi (o'chirilmaydi)
- **▶️ Yoqish** — qaytadan ishga tushiradi
- **🔄 Qayta kirish** — sessiya tugaganda ishlatiladi
- **🗑 O'chirish** — profilni ro'yxatdan butunlay olib tashlaydi

### To'xtatish va o'chirish — farqi nima?

| | ⏸ To'xtatish | 🗑 O'chirish |
|---|---|---|
| Profil javob beradimi? | Yo'q | Yo'q |
| Ro'yxatda qoladimi? | ✅ Ha | ❌ Yo'q |
| Qaytarish oson? | ✅ Bir tugma — «▶️ Yoqish» | ❌ Boshidan qo'shish kerak (kod, parol) |
| Qachon ishlatiladi? | Vaqtincha kerak bo'lmasa | Profil butunlay kerak bo'lmasa |

> 💡 Ikkilanayotgan bo'lsangiz — **to'xtating**, o'chirmang.
> O'chirishdan oldin bot «Ishonchingiz komilmi?» deb so'raydi.

---

## 4. «Qayta kirish kerak» degani nima?

Telegram vaqti-vaqti bilan profillarni tizimdan **chiqarib yuboradi**. Sabablari:

- Telegram sozlamalaridan «barcha seanslarni tugatish» bosilgan
- Akkaunt paroli o'zgartirilgan
- Telegram xavfsizlik tekshiruvi

Bunday holatda bot sizga **o'zi xabar yozadi**:

```
⚠️ acc2 profilidan chiqib ketildi.
Botdan «🔄 Qayta kirish» tugmasini bosing.
```

Siz shunchaki **«🔄 Qayta kirish»** ni bosasiz va yuqoridagi 4–5-qadamlarni
takrorlaysiz (kod, kerak bo'lsa parol). Boshqa hech nima qilish shart emas.

**Muhim:** bitta profil chiqib ketsa ham, qolgan profillar to'xtamaydi.
Ular ishlashda davom etadi.

---

## 5. 💾 Zaxira nusxa (juda muhim)

**«💾 Zaxira nusxa»** tugmasini bossangiz, bot sizga bitta fayl yuboradi.

Bu faylda barcha profillaringiz va ularga kirish kalitlari saqlanadi.
Agar serverda biror falokat yuz bersa — shu fayl orqali hammasi tiklanadi va
profillarni qaytadan qo'shib chiqishga to'g'ri kelmaydi.

**Nima qilish kerak:**
1. Oyiga bir marta **«💾 Zaxira nusxa»** ni bosing
2. Kelgan faylni Telegramdagi **«Saqlangan xabarlar»** ga yuboring

> ⚠️ Bu faylni **hech kimga bermang**. Uni olgan odam sizning Telegram
> profillaringizga kira oladi.

Server o'zi ham har kuni tunda avtomatik zaxira oladi (14 kun saqlanadi),
lekin u serverning o'zida turadi. Shuning uchun oyiga bir marta o'zingiz ham
olib qo'ying — server buzilsa, undagi zaxira ham yo'qoladi.

---

## 6. Buyruqlar (tugmalarga muqobil)

Tugma bosish qulayroq, lekin xohlasangiz buyruq yozsangiz ham bo'ladi:

| Buyruq | Nima qiladi |
|--------|-------------|
| `/menu` | Asosiy menyu |
| `/list` | Profillar ro'yxati |
| `/backup` | Zaxira nusxani yuboradi |
| `/off acc2` | `acc2` ni to'xtatadi |
| `/on acc2` | `acc2` ni qayta yoqadi |
| `/delete acc2` | `acc2` ni butunlay o'chiradi |
| `/status` | Server va profillar holati |
| `/help` | Barcha buyruqlar |

### Boshqa odamga huquq berish

Agar yordamchingiz ham boshqarishini xohlasangiz:

1. U botga `/start` yozsin — bot unga ID sini ko'rsatadi
2. Siz `/addadmin 123456789` deb yozing (ID sini qo'ying)

Olib tashlash: `/deladmin 123456789`

---

## 7. Tez-tez beriladigan savollar

**Kod kelmayapti?**
Telegramning o'zida (boshqa qurilmangizda) «Telegram» nomli rasmiy chatga qarang —
kod o'sha yerga keladi. SMS ham kelishi mumkin.

**«Kod noto'g'ri» deyapti?**
Deyarli har doim sababi bitta: kodni `1-2-3-4-5` emas, `12345` deb yozgansiz.
Chiziqchalar bilan qayta urinib ko'ring.

**«Kodning muddati tugadi» deyapti?**
Kod bir necha daqiqadan keyin eskiradi. Boshidan boshlang — bot yangi kod yuboradi.

**Serverni o'chirib-yoqish kerakmi?**
Yo'q. Hech qachon. Hamma narsa botdan boshqariladi.

**Botni boshqa odam topib ishlata oladimi?**
Yo'q. Botni faqat siz boshqara olasiz — sizning Telegram hisobingiz ro'yxatga
olingan. Boshqa odam yozsa «⛔ Sizda ruxsat yo'q» degan javob oladi.

---

## 8. Yordam kerak bo'lsa

Agar profil ❌ holatida qolsa yoki bot javob bermay qolsa — dasturchiga murojaat
qiling va unga botdagi xato matnini yuboring.
