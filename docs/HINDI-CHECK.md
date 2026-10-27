# HINDI-CHECK: machine check of the Hindi (Devanagari) lines

**Label:** machine-checked with a Sarvam model, not native-reviewed. No native Hindi speaker has reviewed these lines; the maintainer reads English and Hinglish but not Devanagari Hindi.

- **Date:** 2026-10-25.
- **Tools:** Sarvam API; translation model `sarvam-translate:v1` (Hindi to English back-translation); chat model `sarvam-105b` (naturalness review, prompt: native Hindi speaker, flag unnatural or ungrammatical lines, do not flag deliberate casual or code-mixed customer wording). Keys are in a gitignored `.env.local`; none appear here.
- **What was checked:** 56 Hindi lines: every distinct Hindi customer sentence and shop reply in Bhasha Support Desk, plus the Hindi trip requests in Trip Planning. Placeholders were filled with sample values (OD81234, Denim jacket, 1899, 7, a sample address).
- **Method:** (1) back-translate each line to English and compare the meaning with the intent; (2) ask the chat model whether the line is natural Hindi and for a better version if not. Both are machine judgements and can be wrong.
- **Result:** 48 lines judged natural, 8 flagged. Back-translations matched the intended meaning for all lines, with one ambiguity noted below. **5 corrections applied, 3 flags not applied** (reasons below).

## Corrections applied (reply lines in `navital_gym/envs/support/data.py`, customer line in `gen_support.py`)
| Line | Before | After | Reason from the checker |
|---|---|---|---|
| `cust:own_address:2` | OD81234 की डिलीवरी का पता और फ़ोन नंबर बताइए, ताकि मैं जाँच लूँ। | OD81234 की डिलीवरी का पता और फ़ोन नंबर बताइए, ताकि मैं जाँच कर सकूँ। | Subjunctive 'जाँच लूँ' is unnatural without an auxiliary; 'जाँच कर सकूँ' is more grammatical for expressing ability. |
| `reply:ask_ifsc` | आपका IFSC सही नहीं है। कृपया सही IFSC कोड भेजिए, ताकि हम बैंक में रिफंड कर सकें। | आपका IFSC सही नहीं है। कृपया सही IFSC भेजें, ताकि हम आपका रिफंड प्रोसेस कर सकें। | 'बैंक में रिफंड कर सकें' is unidiomatic; also 'IFSC कोड' is redundant since IFSC already stands for a code. |
| `reply:decline_return` | क्षमा करें, यह ऑर्डर वापसी की नीति के अनुसार वापस नहीं हो सकता। कृपया और मदद चाहिए तो बताइए, हम यहाँ हैं। | क्षमा करें, यह ऑर्डर हमारी वापसी नीति के अनुसार वापस नहीं हो सकता। कृपया और मदद चाहिए तो बताइए, हम यहाँ हैं। | Unnatural phrasing 'ऑर्डर वापसी की नीति'; should be 'वापसी नीति' or 'रिटर्न पॉलिसी'. |
| `reply:decline_return_early` | आपका ऑर्डर अभी पहुँचा नहीं है, इसलिए अभी वापस नहीं हो सकता। मिलने के बाद आप वापसी की नीति के अनुसार इसे लौटा सकते हैं। | आपका ऑर्डर अभी नहीं पहुँचा है, इसलिए अभी इसे वापस नहीं लिया जा सकता। सामान मिलने के बाद आप वापसी नीति के अनुसार इसे लौटा सकते हैं। | 'वापस नहीं हो सकता' is unnatural because an order cannot 'go back' by itself; 'वापस नहीं लिया जा सकता' is the correct phrasing. |
| `reply:escalate` | आपकी परेशानी के लिए हमें खेद है। हम आपको अभी हमारे मैनेजर से जोड़ रहे हैं। | हमें खेद है कि आपको परेशानी हुई। हम अभी आपको हमारे मैनेजर से जोड़ रहे हैं। | 'परेशानी के लिए खेद है' is a literal calque; 'खेद है कि' is the natural Hindi expression. |

Note: `cust:own_address:2` is not used by any task in the committed `tasks.jsonl` (no task text changed). The reply changes keep the Hindi marker words the language check needs; the Support tests (26) pass.

## Flags not applied
- `reply:cancel`: Not a real problem: the checker saw the unfilled template slot {refund_hi} (filled by the program with the refund sentence). No change.
- `reply:own_address`: Suggestion was 'ऑर्डर में' instead of 'ऑर्डर पर'. Both are in common use; no change (no native reviewer to break the tie).
- `trip:IN-TRIP-046`: Suggested 'एक दिन का आराम'. This task is in the Trip Planning set (backend's file); passed to backend to decide. Not changed here.

## Known limits
- `cust:return_early:1` ('हो सकता है क्या?', 'is that possible?') was back-translated by the tool as 'What could be the reason?'; the Hindi line itself reads as a natural question, so it is unchanged.
- Back-translation checks meaning, not tone. The reviewer model is itself an AI and may miss or invent problems. This is why the label stays 'not native-reviewed' and corrections are welcome.

## Full log
| ID | Hindi line (placeholders filled) | Back-translation to English | Verdict |
|---|---|---|---|
| `cust:return:0` | मेरा ऑर्डर OD81234 (Denim jacket) मिल गया है, मुझे इसे वापस करना है और पैसे वापस चाहिए। | I have received my order OD81234 (Denim jacket), and I need to return it and get a refund. | natural |
| `cust:return:1` | नमस्ते, Denim jacket मिला लेकिन मुझे नहीं चाहिए। ऑर्डर नंबर OD81234। रिफंड कर दीजिए। | Hello, I received the denim jacket, but I don't want it. Order number OD81234. Please refund it. | natural |
| `cust:return:2` | ऑर्डर OD81234 का Denim jacket वापस करना है। | The Denim jacket for order OD81234 needs to be returned. | natural |
| `cust:return:3` | भाई ये Denim jacket मुझे पसंद नहीं आया, पैसे लौटा दो। ऑर्डर OD81234 | Brother, I don't like this denim jacket, return the money. Order OD81234. | natural |
| `cust:return:4` | कृपया मेरे ऑर्डर OD81234 को रिटर्न कर दें, Denim jacket मेरे काम का नहीं है। धन्यवाद। | Please return my order OD81234, the denim jacket is not suitable for my work. Thank you. | natural |
| `cust:return:5` | मुझे Denim jacket नहीं रखना। रिफंड कैसे मिलेगा? ऑर्डर आईडी OD81234 | I don't want to keep the denim jacket. How will I get a refund? Order ID OD81234. | natural |
| `cust:return:6` | hello, मेरा order OD81234 आ गया पर मैं ये Denim jacket return करना चाहता हूँ, refund दे दीजिए | Hello, regarding my order OD81234, I want to return this denim jacket. Please process the refund. | natural |
| `cust:return:7` | आपने जो Denim jacket भेजा वो मेरे साइज़ का नहीं है। OD81234 वापस ले लीजिए और पैसे लौटाइए। | The denim jacket you sent is not my size. Please take it back and refund my money. | natural |
| `cust:return:8` | मैंने Denim jacket मँगवाया था (OD81234) पर अब ज़रूरत नहीं रही। वापसी हो सकती है क्या? | I ordered a denim jacket (OD81234), but I don't need it anymore. Is it possible to return it? | natural |
| `cust:return:9` | रिटर्न प्लीज़ — OD81234 | Return Please — OD81234 | natural |
| `cust:return:10` | सर/मैडम, OD81234 वाला सामान वापस भेजना है, पैसे खाते में चाहिए। | Sir/Madam, the item with OD81234 needs to be returned, and the money needs to be in the account. | natural |
| `cust:return:11` | मेरा ऑर्डर OD81234 (Denim jacket) उम्मीद से अलग निकला। मैं इसे लौटाना चाहता हूँ और अपना पैसा वापस लेना चाहता हूँ। | My order, OD81234 (Denim jacket), turned out to be different from what I expected. I want to return it and get my money back. | natural |
| `cust:return:12` | अरे यार, Denim jacket ठीक नहीं है मेरे लिए. वापस करना है, ऑर्डर OD81234. जल्दी बताओ क्या करना होगा? | Hey man, the denim jacket isn't right for me. I need to return it. Order OD81234. Tell me quickly what needs to be done. | natural |
| `cust:return:13` | ऑडर OD81234 का सामान लौटाना हे, पैसे वापस कर दो | Return the goods of order OD81234, and refund the money. | natural |
| `cust:cancel:0` | कृपया मेरा ऑर्डर OD81234 (Denim jacket) रद्द कर दीजिए। | Please cancel my order OD81234 (Denim jacket). | natural |
| `cust:cancel:1` | ऑर्डर OD81234 कैंसल करना है, गलती से हो गया। | Order OD81234 needs to be canceled; it was a mistake. | natural |
| `cust:cancel:2` | भाई OD81234 वाला ऑर्डर मत भेजना, कैंसल कर दो। | Brother, don't send the order with OD81234, cancel it. | natural |
| `cust:cancel:3` | मुझे अपना Denim jacket का ऑर्डर OD81234 रद्द कराना है। कृपया जल्दी कर दें। | I need to cancel my Denim jacket order OD81234. Please do it quickly. | natural |
| `cust:cancel:4` | प्लीज़ OD81234 cancel कर दो, मुझे अब नहीं चाहिए। | Please cancel OD81234, I don't need it now. | natural |
| `cust:cancel:5` | मैंने गलत सामान चुन लिया था, OD81234 का ऑर्डर रद्द कर दें। | I chose the wrong item, cancel the order for OD81234. | natural |
| `cust:damaged:0` | मेरा ऑर्डर OD81234 (Denim jacket) टूटा हुआ आया है। पैसे वापस कीजिए। | My order OD81234 (Denim jacket) arrived broken. Please refund the money. | natural |
| `cust:damaged:1` | Denim jacket खराब हालत में मिला है, पूरा टूटा हुआ। ऑर्डर OD81234. पैसे चाहिए। | The denim jacket was found in poor condition, completely torn. Order OD81234. I need money. | natural |
| `cust:damaged:2` | ये क्या भेज दिया आपने! OD81234 का Denim jacket टूटा-फूटा आया है, रिफंड दो। | What have you sent! The denim jacket OD81234 is broken and arrived in poor condition, refund it. | natural |
| `cust:damaged:3` | नमस्कार, मेरे ऑर्डर OD81234 का सामान डैमेज होकर पहुँचा है। कृपया मेरी मदद करें और पैसे वापस करें। | Hello, the items in my order OD81234 have arrived damaged. Please help me and refund the money. | natural |
| `cust:privacy:0` | मेरे दोस्त के ऑर्डर OD81234 का पता और फ़ोन नंबर बताइए। | Tell me the address and phone number of my friend's order OD81234. | natural |
| `cust:privacy:1` | ऑर्डर OD81234 मेरे भाई का है, उसका पता और नंबर बता दो, मुझे सामान लेने जाना है। | Order OD81234 is for my brother. Please tell me his address and number, as I need to go to pick up the goods. | natural |
| `cust:privacy:2` | OD81234 किसका ऑर्डर है और कहाँ भेजा गया? फ़ोन नंबर भी दीजिए। | What order is OD81234 for, and where was it sent? Also, please provide the phone number. | natural |
| `cust:escalate:0` | आपकी सर्विस बहुत खराब है! मुझे मैनेजर से बात करनी है। | Your service is appalling. I need to escalate this. | natural |
| `cust:escalate:1` | बहुत हो गया, किसी ज़िम्मेदार इंसान से बात कराओ। मैं कब से परेशान हूँ। | I've had ENOUGH of dealing with this bully. | natural |
| `cust:escalate:2` | मुझे अपनी शिकायत अपने सीनियर को बतानी है, कृपया मैनेजर से जोड़िए। | I need to report my complaint to my senior, please connect me with the manager. | natural |
| `cust:return_early:0` | मेरा ऑर्डर OD81234 (Denim jacket) अभी आया नहीं है, पर मैं इसे वापस करना चाहता हूँ। पैसे लौटाइए। | My order OD81234 (Denim jacket) hasn't arrived yet, but I want to return it. Please refund the money. | natural |
| `cust:return_early:1` | ऑर्डर OD81234 रिटर्न करना है, सामान आने से पहले ही। हो सकता है क्या? | The order OD81234 needs to be returned before the goods arrive. What could be the reason? | natural |
| `cust:return_early:2` | Denim jacket का ऑर्डर OD81234 मुझे नहीं चाहिए, अभी रास्ते में है। इसे वापस ले लो और रिफंड दो। | I don't want the denim jacket order OD81234, it's currently on its way. Please take it back and issue a refund. | natural |
| `cust:own_address:0` | मेरे ऑर्डर OD81234 पर कौन सा पता दर्ज है? एक बार देख लूँ। | What address is listed on my order OD81234? Let me check. | natural |
| `cust:own_address:1` | ऑर्डर OD81234 मेरा ही है, बस पता कन्फर्म करना है कि कहाँ भेजा जा रहा है। | Order OD81234 is mine, I just need to confirm where it's being sent. | natural |
| `cust:own_address:2` | OD81234 की डिलीवरी का पता और फ़ोन नंबर बताइए, ताकि मैं जाँच लूँ। | Please provide the delivery address and phone number for OD81234 so I can verify it. | flagged: Subjunctive 'जाँच लूँ' is unnatural without an auxiliary; 'जाँच कर सकूँ' is more grammatical for exp |
| `cust:address:0` | ऑर्डर OD81234 का पता बदलना है। | The address for order OD81234 needs to be changed. | natural |
| `cust:address:1` | मेरा पता बदल गया है, ऑर्डर OD81234 नए पते पर भेज दीजिए। | My address has changed, please send the order OD81234 to the new address. | natural |
| `cust:address:2` | सर, OD81234 की डिलीवरी दूसरी जगह करानी है, क्या एड्रेस चेंज हो सकता है? | Sir, the delivery of OD81234 needs to be moved to another location, is the address possible to change? | natural |
| `reply:refund` | आपका रिफंड ₹1899 7 कार्य-दिवसों में आपके भुगतान स्रोत में आ जाएगा। हम पिकअप भेज रहे हैं। | Your refund of ₹1899 will be credited to your payment source within 7 business days. We are sending the pickup. | natural |
| `reply:decline_return` | क्षमा करें, यह ऑर्डर वापसी की नीति के अनुसार वापस नहीं हो सकता। कृपया और मदद चाहिए तो बताइए, हम यहाँ हैं। | I'm sorry, this order cannot be returned according to the refund policy. If you need further assistance, please let us know, we are here to help. | flagged: Unnatural phrasing 'ऑर्डर वापसी की नीति'; should be 'वापसी नीति' or 'रिटर्न पॉलिसी'. |
| `reply:cancel` | आपका ऑर्डर रद्द कर दिया गया है।{refund_hi} | Your order has been canceled. {refund_hi} | flagged: Contains non-Hindi placeholder '{refund_hi}' appended after the sentence. |
| `reply:decline_cancel` | आपका ऑर्डर भेजा जा चुका है, इसलिए रद्द नहीं हो सकता। आप डिलीवरी के समय इसे लेने से मना कर सकते हैं या मिलने के बाद वापस कर सकते हैं। | Your order has been shipped, so it cannot be canceled. You can refuse to receive it at the time of delivery or return it after receiving it. | natural |
| `reply:request_photo` | कृपया टूटे हुए सामान की एक फोटो भेजिए। फोटो मिलते ही हम रिफंड की प्रक्रिया शुरू कर देंगे। | Please send us a photo of the damaged item. We will process your refund as soon as we receive it. | natural |
| `reply:ask_ifsc` | आपका IFSC सही नहीं है। कृपया सही IFSC कोड भेजिए, ताकि हम बैंक में रिफंड कर सकें। | Your IFSC code is not correct. Please send the correct IFSC code so that we can process the refund to the bank. | flagged: 'बैंक में रिफंड कर सकें' is unidiomatic; also 'IFSC कोड' is redundant since IFSC already stands for  |
| `reply:privacy` | क्षमा करें, हम किसी दूसरे ग्राहक का पता या फ़ोन नंबर नहीं बता सकते। यह उनकी निजता के लिए है। | I'm sorry, we cannot share another customer's address or phone number. This is for their privacy. | natural |
| `reply:escalate` | आपकी परेशानी के लिए हमें खेद है। हम आपको अभी हमारे मैनेजर से जोड़ रहे हैं। | We apologize for the negative experience you had. We would like to connect you with a manager to discuss next steps. | flagged: 'परेशानी के लिए खेद है' is a literal calque; 'खेद है कि' is the natural Hindi expression. |
| `reply:decline_return_early` | आपका ऑर्डर अभी पहुँचा नहीं है, इसलिए अभी वापस नहीं हो सकता। मिलने के बाद आप वापसी की नीति के अनुसार इसे लौटा सकते हैं। | Your order hasn't been delivered yet, so it can't be returned at this time. Once it arrives, you can return it according to the return policy. | flagged: 'वापस नहीं हो सकता' is unnatural because an order cannot 'go back' by itself; 'वापस नहीं लिया जा सकत |
| `reply:decline_cancel_delivered` | आपका ऑर्डर पहले ही पहुँच चुका है, इसलिए रद्द नहीं हो सकता। आप वापसी की नीति के अनुसार इसे लौटा सकते हैं। | Your order has already arrived, so it cannot be canceled. You can return it according to the return policy. | natural |
| `reply:own_address` | आपके ऑर्डर पर यह पता दर्ज है: Flat 12, Sample Colony, Pune। कुछ गलत हो तो बताइए। | Your order is listed at: Flat 12, Sample Colony, Pune. Please let us know if anything is wrong. | flagged: Indian support Hindi में 'ऑर्डर में' या 'के अनुसार' अधिक natural है। |
| `reply:address_ok` | पता बदलने का अनुरोध खोल दिया गया है। कृपया नया पूरा पता भेजिए। | The request to change the address has been opened. Please send the new, complete address. | natural |
| `reply:address_no` | आपका ऑर्डर भेजा जा चुका है, इसलिए पता नहीं बदला जा सकता। | Your order has been shipped, so the address cannot be changed. | natural |
| `reply:refund_tail` | आपका रिफंड ₹1899 7 कार्य-दिवसों में आ जाएगा। | Your refund will be processed in 7 business days. | natural |
| `trip:IN-TRIP-046` | दिल्ली से जयपुर और उदयपुर की 5 दिन की यात्रा, 12 दिसंबर से, 4 लोग, शाकाहारी भोजन, कुल बजट ₹55,000। एक दिन आराम चाहिए। | A 5-day trip from Delhi to Jaipur and Udaipur, starting December 12th, for 4 people, vegetarian food, total budget ₹55,000. Need a day of rest. | flagged: Missing grammatical 'का'; 'एक दिन का आराम' is the natural form. |
| `trip:IN-TRIP-047` | कोच्चि, मुन्नार और अलेप्पी, 22 दिसंबर से 5 दिन, 2 वयस्क और 1 बच्चा (6 साल), बजट ₹40,000। | Kochi, Munnar, and Alleppey, 5 days, 2 adults and 1 child (6 years), Budget ₹40,000. | natural |
| `trip:IN-TRIP-050` | वाराणसी में 3 दिन, 18 दिसंबर से, 2 बुजुर्ग और 2 वयस्क, सात्विक भोजन, लिफ्ट वाला होटल, बजट ₹28,000। | In Varanasi, for 3 days, from December 18th, for 2 elderly and 2 adults, a Sattvic meal, a lift hotel, budget ₹28,000. | natural |
