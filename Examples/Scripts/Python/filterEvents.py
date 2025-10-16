import csv

import ROOT


mHist = ROOT.TH1F("mHist", "mHist", 25, 1.5, 2.0)



for y in range(0,50):


    folder = 'odd_output_tau3mu_run_%d/'%y


    for i in range(0,2000):

    
        nMuons = 0
        muonPx = []
        muonPy = []
        muonPz = []
        muonM = []
        with open(folder + f'event00000{i:04d}-particles_simulated.csv', mode='r', newline='') as file:
            csv_dict_reader = csv.DictReader(file)
            for index, row in enumerate(csv_dict_reader):
                if abs(int(row['particle_type'])) == 13 and int(row['particle_id_pv']) == 1: 
                    muonPx.append(float(row['px']))
                    muonPy.append(float(row['py']))
                    muonPz.append(float(row['pz']))
                    muonM.append(float(row['m']))
                    nMuons += 1

            if nMuons == 3:
                v1 = ROOT.TLorentzVector()
                v2 = ROOT.TLorentzVector()
                v3 = ROOT.TLorentzVector()

                e1 = (muonPx[0]**2 + muonPy[0]**2 + muonPz[0]**2 + muonM[0]**2)**0.5
                e2 = (muonPx[1]**2 + muonPy[1]**2 + muonPz[1]**2 + muonM[1]**2)**0.5
                e3 = (muonPx[2]**2 + muonPy[2]**2 + muonPz[2]**2 + muonM[2]**2)**0.5

                v1.SetPxPyPzE(muonPx[0], muonPy[0], muonPz[0], e1)
                v2.SetPxPyPzE(muonPx[1], muonPy[1], muonPz[1], e2)
                v3.SetPxPyPzE(muonPx[2], muonPy[2], muonPz[2], e3)


                tau = v1 + v2 + v3
                mHist.Fill(tau.M())


c1 = ROOT.TCanvas('c1', 'c1', 800, 800)


mHist.Draw("hist")

c1.Print("tauMass.pdf")

