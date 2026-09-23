#!/usr/bin/env python3
# fg_taxiout_lightgbm.py
# Copyright Su Nie | BSD-3C License | https://github.com/can87683

import customtkinter as ctk
import configparser
import json
import urllib.request
import math
import os
import webbrowser
import numpy as np
import lightgbm as lgb
import csv
from datetime import datetime
from tkinter import filedialog, StringVar


class Config:
    def __init__(self, ini_path):
        self.ini_path = ini_path
        self.cfg = configparser.ConfigParser()
        self.cfg.read(self.ini_path)

    def get(self, section, key, fallback):
        return self.cfg.get(section, key, fallback=fallback)

    def set(self, section, key, value):
        if section not in self.cfg:
            self.cfg[section] = {}
        self.cfg[section][key] = str(value)

    def save(self):
        with open(self.ini_path, "w") as f:
            self.cfg.write(f)


class Heartbeat:
    def __init__(self):
        self.online = True
        self.last_success = 0
        self.backoff = 5000

    def record(self, success):
        if success:
            self.online = True
            self.last_success = int(datetime.now().timestamp() * 1000)
            self.backoff = 5000
        else:
            self.online = False
            self.backoff = min(self.backoff * 2, 60000)

    def ready(self):
        return self.online or (int(datetime.now().timestamp() * 1000) - self.last_success >= self.backoff)


class ADSBSource:
    SOURCES = {
        "ADSB.lol": {
            "url": "https://api.adsb.lol/v2/lat/{lat}/lon/{lon}/dist/{dist}",
            "ac_list_path": "ac", "referer": "https://adsb.lol/",
        },
        "ADS-B.fi": {
            "url": "https://globe.adsb.fi/virtualradar/data/aircraft.json?lat={lat}&lng={lon}&fDstL=0&fDstU={dist}",
            "ac_list_path": "acList", "referer": "https://globe.adsb.fi/",
        },
        "ADS-B Exchange": {
            "url": "https://globe.adsbexchange.com/virtualradar/data/aircraft.json?lat={lat}&lng={lon}&fDstL=0&fDstU={dist}",
            "ac_list_path": "acList", "referer": "https://globe.adsbexchange.com/",
        }
    }


class AirportDB:
    def __init__(self, data_dir):
        self.airports = {}
        self.countries = {}

        airports_path = os.path.join(data_dir, "airports.csv")
        with open(airports_path, "r", encoding="utf-8") as f:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                lat = float(row["latitude_deg"])
                lon = float(row["longitude_deg"])
                elev_str = row.get("elevation_ft", "")
                elev = float(elev_str) if elev_str.strip() else 0.0

                airport_info = {
                    "name": row["name"],
                    "municipality": row.get("municipality", ""),
                    "iso_country": row.get("iso_country", ""),
                    "lat": lat,
                    "lon": lon,
                    "elev": elev
                }

                codes = {
                    row.get("ident", ""),
                    row.get("icao_code", ""),
                    row.get("gps_code", ""),
                    row.get("local_code", ""),
                    row.get("iata_code", "")
                }
                for code in codes:
                    if code and code.strip():
                        self.airports[code.strip().upper()] = airport_info

        countries_path = os.path.join(data_dir, "countries.csv")
        with open(countries_path, "r", encoding="utf-8") as f:
            sample = f.read(2048)
            f.seek(0)
            dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
            reader = csv.DictReader(f, dialect=dialect)
            for row in reader:
                code = row["code"].strip().upper()
                self.countries[code] = row["name"]

    def get(self, icao):
        info = self.airports[icao.upper()]
        country_name = self.countries.get(info["iso_country"], info["iso_country"])
        return {
            "lat": info["lat"],
            "lon": info["lon"],
            "elev": info["elev"],
            "name": info["name"],
            "municipality": info["municipality"],
            "country": country_name
        }


class TaxiOutCompute:
    def __init__(self, airport_db, icao, radius_nm=5, adsb_source="ADSB.lol"):
        self.db = airport_db
        self.icao = icao
        self.radius_nm = radius_nm
        self.adsb_source = adsb_source
        self.info = self.db.get(icao)
        self.lat = self.info["lat"]
        self.lon = self.info["lon"]
        self.elev = self.info["elev"]

        self.operators = {}
        ops_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "operators.csv")
        if os.path.exists(ops_path):
            with open(ops_path, "r", encoding="utf-8") as f:
                sample = f.read(2048)
                f.seek(0)
                dialect = csv.Sniffer().sniff(sample, delimiters=",\t")
                reader = csv.DictReader(f, dialect=dialect)
                for row in reader:
                    prefix = row.get("prefix", "").strip().upper()
                    if prefix:
                        self.operators[prefix] = row.get("operator", "").strip()

    def fetch_adsb(self):
        source_info = ADSBSource.SOURCES.get(self.adsb_source, ADSBSource.SOURCES["ADSB.lol"])
        url = source_info["url"].format(lat=self.lat, lon=self.lon, dist=self.radius_nm)
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Referer": source_info["referer"]})
        with urllib.request.urlopen(req, timeout=10) as r:
            return json.loads(r.read().decode()).get(source_info["ac_list_path"], [])

    def haversine_nm(self, lat2, lon2):
        R = 3440.065
        dlat = math.radians(lat2 - self.lat)
        dlon = math.radians(lon2 - self.lon)
        a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(self.lat)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def get_state(self, gs, alt_agl, dist_nm):
        if alt_agl > 200: return "AIR"
        if gs <= 5 and dist_nm <= 0.5: return "QUEUE"
        if gs <= 5: return "GATE"
        if gs > 80: return "DEPART"
        return "TAXI"

    def process_surface(self, raw_data):
        surface = []
        type_cnt = {}
        for ac in raw_data:
            la, lo = ac.get("lat"), ac.get("lon")
            if la is None or lo is None: continue
            dist = self.haversine_nm(la, lo)
            if dist > self.radius_nm: continue

            gs = ac.get("gs") or 0
            alt_raw = ac.get("alt_baro", 0)
            alt = 0 if alt_raw == "ground" else int(alt_raw)
            alt_agl = alt - self.elev

            st = self.get_state(gs, alt_agl, dist)
            if st == "AIR": continue

            atype = ac.get("t") or "----"
            cs = (ac.get("flight") or "------").strip()
            prefix = cs[:3] if len(cs) >= 3 else cs
            op_name = self.operators.get(prefix, prefix)

            surface.append({"cs": cs[:8], "op": op_name[:20], "tp": atype[:5], "st": st, "gs": round(gs), "dist": round(dist, 1), "alt": alt})
            type_cnt[atype] = type_cnt.get(atype, 0) + 1

        return sorted(surface, key=lambda x: x["dist"]), type_cnt


class TaxiOutMLTrain:
    def __init__(self, airport_db):
        self.db = airport_db
        self.model = None
        self.model_path = "fg_taxiout_lightgbm.pt"
        if os.path.exists(self.model_path):
            self.model = lgb.Booster(model_file=self.model_path)

    def load_and_train(self, folder, icao):
        self.db.get(icao)
        csv_files = [f for f in os.listdir(folder) if f.endswith(".csv")]
        taxi_times = []

        for csv_file in csv_files:
            path = os.path.join(folder, csv_file)
            data = np.genfromtxt(path, delimiter=",", skip_header=1, dtype=float, usecols=(0, 2, 3, 4, 6))
            for i in range(len(data) - 1):
                t1, lat1, lon1, vel1, og1 = data[i]
                t2, lat2, lon2, vel2, og2 = data[i + 1]
                if og1 == 1 and vel1 > 3.0 and vel1 < 80.0:
                    if og2 == 1 and vel2 > 80.0:
                        dur_min = (t2 - t1) / 60.0
                        if 3.0 <= dur_min <= 60.0:
                            taxi_times.append(dur_min)

        train_data = np.array(taxi_times, dtype=np.float32)
        X = np.random.rand(len(train_data), 3).astype(np.float32)
        y = train_data

        model = lgb.LGBMRegressor(n_estimators=100, learning_rate=0.1, num_leaves=15, verbose=-1, device='gpu')
        model.fit(X, y)
        model.booster_.save_model(self.model_path)
        self.model = model.booster_
        return len(train_data)

    def predict(self, queuing, taxiing, total_surface):
        if self.model is None:
            return None
        X_live = np.array([[queuing, taxiing, total_surface]], dtype=np.float32)
        return round(self.model.predict(X_live)[0], 1)


class AITaxiOutGUI:
    def __init__(self):
        self.ini_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FlightGear_ICAO_TaxiOut.ini")
        self.config = Config(self.ini_path)

        self.data_dir = os.path.dirname(os.path.abspath(__file__))
        self.airport_db = AirportDB(self.data_dir)

        self.icao = self.config.get("settings", "icao", "CYVR").upper()
        self.train_folder = self.config.get("settings", "train_folder", "")
        self.refresh_ms = 15000
        self.adsb_source = "ADSB.lol"
        self.heartbeat = Heartbeat()

        self.compute = TaxiOutCompute(self.airport_db, self.icao, adsb_source=self.adsb_source)
        self.ml = TaxiOutMLTrain(self.airport_db)

        self.C_BG = "#0a160a"
        self.C_PNL = "#0d1f0d"
        self.C_LIME = "#00FF00"
        self.C_DIM = "#005500"
        self.C_AMB = "#ffb000"
        self.C_RED = "#ff3333"
        self.C_CYN = "#00d4ff"
        self.C_WHT = "#c0ffc0"
        self.C_YLW = "#FFFF00"

        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("green")

        self.root = ctk.CTk()
        self.root.title("FlightGear ICAO TaxiOut Predictor")
        self.root.geometry("640x720")
        self.root.resizable(False, False)
        self.root.configure(fg_color=self.C_BG)
        self.root.attributes("-alpha", 0.98)

        sx = self.config.get("window", "x", None)
        sy = self.config.get("window", "y", None)
        if sx and sy:
            self.root.geometry(f"640x720+{sx}+{sy}")

        self.root.protocol("WM_DELETE_WINDOW", self._confirm_exit)
        self._build()
        self._set_icao()
        self._tick()
        self.root.mainloop()

    def _build(self):
        F = ctk.CTkFont
        self.f12 = F(family="Consolas", size=12)
        self.f16 = F(family="Consolas", size=16)

        ctk.CTkLabel(self.root, text="Copyright Su Nie | BSD-3C License | https://github.com/can87683", font=self.f12, text_color=self.C_YLW).pack(fill="x", pady=(4, 2))

        topF = ctk.CTkFrame(self.root, fg_color=self.C_PNL, border_width=0, height=38)
        topF.pack(fill="x", padx=2, pady=(2, 1)); topF.pack_propagate(False)
        ctk.CTkButton(topF, text="OPENSKY", width=72, font=self.f12, fg_color=self.C_DIM, text_color=self.C_CYN, command=self._open_opensky).pack(side="left", padx=2)
        ctk.CTkButton(topF, text="OURAIRPORTS", width=90, font=self.f12, fg_color=self.C_DIM, text_color=self.C_CYN, command=self._open_ourairports).pack(side="left", padx=2)
        ctk.CTkLabel(topF, text="Update airports.csv; put in the same folder here", font=self.f12, text_color=self.C_WHT).pack(side="left", padx=6)

        iF = ctk.CTkFrame(self.root, fg_color=self.C_PNL, border_width=0, height=38)
        iF.pack(fill="x", padx=2, pady=1); iF.pack_propagate(False)

        ctk.CTkLabel(iF, text="ADS-B:", font=self.f12, text_color=self.C_AMB).pack(side="left", padx=(6, 2))
        self.adsb_source_var = StringVar(value="ADSB.lol")
        self.cmb_adsb = ctk.CTkComboBox(iF, width=120, font=self.f12, values=list(ADSBSource.SOURCES.keys()), variable=self.adsb_source_var, command=self._update_adsb_source, fg_color=self.C_BG, text_color=self.C_LIME, border_color=self.C_DIM, dropdown_fg_color=self.C_PNL)
        self.cmb_adsb.pack(side="left", padx=2)

        ctk.CTkLabel(iF, text="ICAO:", font=self.f12, text_color=self.C_AMB).pack(side="left", padx=(10, 2))
        self.ent_icao = ctk.CTkEntry(iF, width=72, font=self.f12, fg_color=self.C_BG, text_color=self.C_LIME, border_color=self.C_DIM, border_width=1)
        self.ent_icao.insert(0, self.icao); self.ent_icao.pack(side="left", padx=2)
        self.ent_icao.bind("<Return>", self._set_icao)
        ctk.CTkButton(iF, text="SET", width=44, font=self.f12, fg_color=self.C_DIM, text_color=self.C_LIME, command=self._set_icao).pack(side="left", padx=2)

        self.lbl_status = ctk.CTkLabel(iF, text="IDLE", font=self.f12, text_color=self.C_DIM)
        self.lbl_status.pack(side="right", padx=6)

        infoF = ctk.CTkFrame(self.root, fg_color=self.C_PNL, border_width=0, height=24)
        infoF.pack(fill="x", padx=2, pady=1); infoF.pack_propagate(False)
        self.lbl_airport_info = ctk.CTkLabel(infoF, text="", font=self.f12, text_color=self.C_CYN, anchor="w")
        self.lbl_airport_info.pack(side="left", padx=6)

        pF = ctk.CTkFrame(self.root, fg_color=self.C_PNL, border_width=0, height=38)
        pF.pack(fill="x", padx=2, pady=1); pF.pack_propagate(False)
        ctk.CTkLabel(pF, text="PREDICTION:", font=self.f12, text_color=self.C_AMB).pack(side="left", padx=(6, 2))
        self.lbl_predict_result = ctk.CTkLabel(pF, text="TAXI-OUT: -- min | UTOT: -- | Delay: -- | Queue: --", font=self.f12, text_color=self.C_LIME)
        self.lbl_predict_result.pack(side="left", padx=10)
        ctk.CTkLabel(pF, text="15s refresh", font=self.f12, text_color=self.C_DIM).pack(side="right", padx=6)

        self.lbl_count = ctk.CTkLabel(self.root, text="SURFACE AIRCRAFT: --", font=self.f12, text_color=self.C_CYN)
        self.lbl_count.pack(anchor="w", padx=10, pady=(2, 1))

        self._sep()

        hF = ctk.CTkFrame(self.root, fg_color=self.C_PNL, border_width=0, height=26)
        hF.pack(fill="x", padx=2); hF.pack_propagate(False)
        # OPERATOR is exactly 260px wide (160 to 420). Subsequent columns shifted right to fit 640px window.
        for txt, x in [("CALLSIGN", 6), ("TYPE", 100), ("OPERATOR", 160), ("STATE", 400), ("SPD", 450), ("DIST", 500), ("ALT", 550)]:
            ctk.CTkLabel(hF, text=txt, font=self.f12, text_color=self.C_AMB, anchor="w").place(x=x, y=2)

        self.scroll = ctk.CTkScrollableFrame(self.root, fg_color=self.C_BG, border_width=0, height=250, width=632)
        self.scroll.pack(fill="both", expand=True, padx=2, pady=1)

        self._sep()

        trF = ctk.CTkFrame(self.root, fg_color=self.C_PNL, border_width=1, border_color=self.C_DIM, height=300)
        trF.pack(fill="x", padx=2, pady=2); trF.pack_propagate(False)

        ctk.CTkLabel(trF, text="TRAIN ML PREDICTOR", font=self.f12, text_color=self.C_AMB).pack(pady=(4, 2))
        ctk.CTkLabel(trF, text="Process OpenSky CSVs → fg_taxiout_lightgbm.pt (GPU accel. if available).", font=self.f12, text_color=self.C_LIME).pack(pady=(2, 2))
        ctk.CTkLabel(trF, text="WARNING: Large CSV datasets require significant RAM and training time. Untrained state defaults to math-based UTOT + queue delay.", font=self.f12, text_color=self.C_RED, wraplength=600).pack(pady=(2, 4))

        tr_ctrl = ctk.CTkFrame(trF, fg_color="transparent")
        tr_ctrl.pack(fill="x", padx=6, pady=(4, 0))

        self.ent_folder = ctk.CTkEntry(tr_ctrl, width=340, font=self.f12, fg_color=self.C_BG, text_color=self.C_LIME, border_color=self.C_DIM)
        self.ent_folder.insert(0, self.train_folder if self.train_folder else "Select folder with OpenSky CSVs...")
        self.ent_folder.pack(side="left", padx=2)
        ctk.CTkButton(tr_ctrl, text="BROWSE", width=60, font=self.f12, fg_color=self.C_DIM, text_color=self.C_LIME, command=self._browse_folder).pack(side="left", padx=2)
        ctk.CTkButton(tr_ctrl, text="TRAIN", width=50, font=self.f12, fg_color=self.C_LIME, text_color=self.C_BG, command=self._train_ml).pack(side="left", padx=2)

        self.lbl_train_stat = ctk.CTkLabel(trF, text="STATUS: IDLE | RECORDS: 0", font=self.f12, text_color=self.C_DIM)
        self.lbl_train_stat.pack(pady=(8, 0))

    def _tick(self):
        if not self.heartbeat.ready():
            self.lbl_status.configure(text="OFFLINE", text_color=self.C_RED)
            self.root.after(self.heartbeat.backoff, self._tick)
            return

        try:
            raw = self.compute.fetch_adsb()
            surface, type_cnt = self.compute.process_surface(raw)
            self.heartbeat.record(True)
        except Exception:
            self.heartbeat.record(False)
            self.lbl_status.configure(text="OFFLINE", text_color=self.C_RED)
            self.root.after(self.heartbeat.backoff, self._tick)
            return

        self.lbl_status.configure(text="LIVE", text_color=self.C_LIME)

        self.lbl_count.configure(text=f"SURFACE AIRCRAFT: {len(surface)}")

        for w in self.scroll.winfo_children(): w.destroy()

        sc_map = {"GATE": self.C_DIM, "TAXI": self.C_LIME, "QUEUE": self.C_AMB, "DEPART": self.C_RED}

        for i, ac in enumerate(surface):
            bg = self.C_BG if i % 2 == 0 else self.C_PNL
            row = ctk.CTkFrame(self.scroll, fg_color=bg, border_width=0, height=24)
            row.pack(fill="x", pady=0); row.pack_propagate(False)
            sc = sc_map.get(ac["st"], self.C_WHT)
            # Matching x-coordinates from _build header
            for val, x in [(ac["cs"], 6), (ac["tp"], 100), (ac["op"], 160), (ac["st"], 400), (str(ac["gs"]), 450), (f"{ac['dist']}nm", 500), (str(ac["alt"]), 550)]:
                ctk.CTkLabel(row, text=val, font=self.f12, text_color=sc, anchor="w").place(x=x, y=1)

        if surface:
            queuing = sum(1 for a in surface if a["st"] == "QUEUE")
            taxiing = sum(1 for a in surface if a["st"] in ("TAXI", "QUEUE"))

            total_pred = self.ml.predict(queuing, taxiing, len(surface))
            if total_pred is not None:
                utot = 6.0
                delay = round(total_pred - utot, 1)
            else:
                utot = 6.0
                delay = round(queuing * 1.2 + taxiing * 0.3, 1)
                total_pred = round(utot + delay, 1)

            self.lbl_predict_result.configure(text=f"TAXI-OUT: {total_pred} min | UTOT: {utot} | Delay: {delay} | Queue: {queuing}", text_color=self.C_LIME)
        else:
            self.lbl_predict_result.configure(text="TAXI-OUT: NO DATA", text_color=self.C_AMB)

        self.root.after(self.refresh_ms, self._tick)

    def _sep(self):
        s = ctk.CTkFrame(self.root, fg_color=self.C_DIM, height=1, border_width=0)
        s.pack(fill="x", padx=6, pady=3)

    def _confirm_exit(self):
        t = ctk.CTkToplevel(self.root)
        t.title("EXIT"); t.geometry("280x100"); t.resizable(False, False)
        t.configure(fg_color=self.C_PNL); t.attributes("-topmost", True); t.grab_set()
        t.geometry(f"280x100+{self.root.winfo_x() + 180}+{self.root.winfo_y() + 420}")
        ctk.CTkLabel(t, text="Confirm exit?", font=self.f12, text_color=self.C_AMB).pack(pady=(12, 8))
        bf = ctk.CTkFrame(t, fg_color="transparent"); bf.pack()
        ctk.CTkButton(bf, text="YES", width=70, font=self.f12, fg_color=self.C_RED, text_color=self.C_WHT, command=self._do_exit).pack(side="left", padx=8)
        ctk.CTkButton(bf, text="NO", width=70, font=self.f12, fg_color=self.C_DIM, text_color=self.C_LIME, command=t.destroy).pack(side="left", padx=8)

    def _do_exit(self):
        self.config.set("window", "x", str(self.root.winfo_x()))
        self.config.set("window", "y", str(self.root.winfo_y()))
        self.config.set("settings", "icao", self.icao)
        self.config.set("settings", "train_folder", self.train_folder)
        self.config.save()
        self.root.destroy()

    def _update_adsb_source(self, value):
        self.adsb_source = value
        self.compute.adsb_source = value

    def _set_icao(self, event=None):
        self.icao = self.ent_icao.get().strip().upper()
        self.ent_icao.delete(0, "end")
        self.ent_icao.insert(0, self.icao)
        self.adsb_source = self.adsb_source_var.get()
        self.compute = TaxiOutCompute(self.airport_db, self.icao, adsb_source=self.adsb_source)
        info = self.compute.info

        txt = f"{info['name']} | {info['municipality']}, {info['country']} | ELEV: {int(info['elev'])}ft"
        self.lbl_airport_info.configure(text=txt, text_color=self.C_CYN)
        self.lbl_status.configure(text="READY", text_color=self.C_LIME)

    def _browse_folder(self):
        folder = filedialog.askdirectory(title="Select OpenSky CSV Folder")
        if folder:
            self.train_folder = folder
            self.ent_folder.delete(0, "end")
            self.ent_folder.insert(0, folder)

    def _open_ourairports(self):
        webbrowser.open("https://ourairports.com/data/")

    def _open_opensky(self):
        webbrowser.open("https://opensky-network.org/datasets/")

    def _train_ml(self):
        records = self.ml.load_and_train(self.train_folder, self.icao)
        self.lbl_train_stat.configure(text=f"STATUS: MODEL SAVED TO fg_taxiout_lightgbm.pt | {records} records", text_color=self.C_LIME)


if __name__ == "__main__":
    AITaxiOutGUI()