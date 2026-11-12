import os, imagegen
P = "Photorealistic documentary news photograph, tall vertical 9:16, a police jeep parked on a misty road near Coimbatore Tamil Nadu at dawn, sharp detail, natural colours, no text"
for model, build in imagegen.CF_MODELS:
    try:
        d = imagegen._cf(model, build(P, 7), os.environ["CLOUDFLARE_API_TOKEN"], os.environ["CLOUDFLARE_ACCOUNT_ID"])
        open("research_free/results/img/" + model.split("/")[-1] + ".jpg", "wb").write(d); print("ok", model, len(d))
    except Exception as e:
        print("FAIL", model, str(e)[:200])
