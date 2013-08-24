#!/usr/bin/env python
import random
import os
import inspect
from numpy import *
from math import cos
from math import sqrt
import IMP
import IMP.em
import IMP.algebra
import cPickle
import time
from numpy import *
from scipy.spatial.distance import cdist
import tools
from copy import deepcopy

kB= (1.381 * 6.02214) / 4184.0

class Stopwatch():

    def __init__(self,isdelta=True):
        self.starttime=time.clock()
        self.label="None"
        self.isdelta=isdelta
    
    def set_label(self,labelstr):
        self.label=labelstr
        
    def get_output(self):
        output={}
        if self.isdelta:
           newtime=time.clock()
           output["Stopwatch_"+self.label+"_delta_seconds"]=str(newtime-self.starttime)
           self.starttime=newtime
        else:
           output["Stopwatch_"+self.label+"_elapsed_seconds"]=str(time.clock()-self.starttime)           
        return output


class SetupNuisance():
    def __init__(self,m,initialvalue,minvalue,maxvalue,isoptimized=True):
        nuisance=IMP.isd2.Scale.setup_particle(IMP.Particle(m),initialvalue)
        nuisance.set_lower(minvalue)
        nuisance.set_upper(maxvalue)

        m.add_score_state(IMP.core.SingletonConstraint(IMP.isd2.NuisanceRangeModifier(),None,nuisance))
        nuisance.set_is_optimized(nuisance.get_nuisance_key(),isoptimized)
        self.nuisance=nuisance

    def get_particle(self):
        return self.nuisance

class SetupWeight():
    import IMP.isd2
    def __init__(self,m,isoptimized=True):
        pw=IMP.Particle(m)
        self.weight=IMP.isd2.Weight.setup_particle(pw)
        self.weight.set_weights_are_optimized(True)

    def get_particle(self):
        return self.weight



class ParticleToSampleList():

    
    def __init__(self,label="None"):
     
        self.dictionary_particle_type={}
        self.dictionary_particle_transformation={}
        self.dictionary_particle_name={}        
        self.label=label
        
    def add_particle(self,particle,particle_type,particle_transformation,name):
        if not particle_type in ["Rigid_Bodies","Floppy_Bodies","Nuisances","X_coord","Weights"]:
           print "ParticleToSampleList: not the right particle type"
           exit()
        else:
           self.dictionary_particle_type[particle]=particle_type
           if particle_type=="Rigid_Bodies":
              if type(particle_transformation)==tuple and len(particle_transformation)==2 and type(particle_transformation[0])==float and type(particle_transformation[1])==float:
                 self.dictionary_particle_transformation[particle]=particle_transformation
                 self.dictionary_particle_name[particle]=name
              else:
                 print "ParticleToSampleList: not the right transformation format for Rigid_Bodies, should be a tuple a floats"
                 exit()                 
           else:
              if type(particle_transformation)==float: 
                 self.dictionary_particle_transformation[particle]=particle_transformation
                 self.dictionary_particle_name[particle]=name                 
              else:
                 print "ParticleToSampleList: not the right transformation format sould be a float"
                 exit()     

    def get_particles_to_sample(self):
        ps={}
        for particle in self.dictionary_particle_type:
           key=self.dictionary_particle_type[particle]+"ParticleToSampleList_"+self.dictionary_particle_name[particle]+"_"+self.label
           value=([particle],self.dictionary_particle_transformation[particle])
           ps[key]=value
        return ps   


class Output():

    def __init__(self,ascii=True):
        self.dictionary_pdbs={}
        self.dictionary_rmfs={}
        self.dictionary_stats={}
        self.best_score_list=None
        self.nbestscoring=None
        self.suffix=None
        self.ascii=ascii
        self.initoutput={}

    def get_pdb_names(self):
        return self.dictionary_pdbs.keys()

    def get_rmf_names(self):
        return self.dictionary_rmfs.keys()

    def get_stat_names(self):
        return self.dictionary_stats.keys()

    def init_pdb(self,name,prot):
        flpdb=open(name,'w')
        flpdb.close()
        self.dictionary_pdbs[name]=prot

    def write_pdb(self,name,appendmode=True):
        if appendmode:
            flpdb=open(name,'a')
        else:
            flpdb=open(name,'w')
        IMP.atom.write_pdb(self.dictionary_pdbs[name],flpdb)
        flpdb.close()

    def write_pdbs(self,appendmode=True):
        for pdb in self.dictionary_pdbs.keys():
            self.write_pdb(pdb,appendmode)

    def init_pdb_best_scoring(self,suffix,prot,nbestscoring):
        # save only the nbestscoring conformations
        # create as many pdbs as needed
        self.best_score_list=[]
        self.suffix=suffix
        self.nbestscoring=nbestscoring
        for i in range(self.nbestscoring):
          name=suffix+"."+str(i)+".pdb"
          flpdb=open(name,'w')
          flpdb.close()
          self.dictionary_pdbs[name]=prot

    def write_pdb_best_scoring(self,score):
        if self.nbestscoring==None:
           print "Output.write_pdb_best_scoring: init_pdb_best_scoring not run"
        
        #update the score list
        if len(self.best_score_list)<self.nbestscoring:
           self.best_score_list.append(score)
           self.best_score_list.sort()
           index=self.best_score_list.index(score)
           for i in range(len(self.best_score_list)-2,index-1,-1):
               oldname=self.suffix+"."+str(i)+".pdb"
               newname=self.suffix+"."+str(i+1)+".pdb"
               os.rename(oldname, newname)
           filetoadd=self.suffix+"."+str(index)+".pdb"
           self.write_pdb(filetoadd,appendmode=False)
           
        else:
           if score<self.best_score_list[-1]:
              self.best_score_list.append(score)
              self.best_score_list.sort()
              self.best_score_list.pop(-1)
              index=self.best_score_list.index(score)
              for i in range(len(self.best_score_list)-1,index-1,-1):
                 oldname=self.suffix+"."+str(i)+".pdb"
                 newname=self.suffix+"."+str(i+1)+".pdb"
                 os.rename(oldname, newname)      
              filenametoremove=self.suffix+"."+str(self.nbestscoring)+".pdb"
              os.remove(filenametoremove)              
              filetoadd=self.suffix+"."+str(index)+".pdb"                   
              self.write_pdb(filetoadd,appendmode=False)              

    def init_rmf(self,name,prot):
        import RMF
        import IMP.rmf
        rh = RMF.create_rmf_file(name)
        IMP.rmf.add_hierarchy(rh, prot)
        self.dictionary_rmfs[name]=rh

    def add_restraints_to_rmf(self,name,objectlist):
        import RMF
        import IMP.rmf
        for o in objectlist:
            rs=o.get_restraint()
            IMP.rmf.add_restraints(self.dictionary_rmfs[name],rs.get_restraints())

    def write_rmf(self,name,nframe):
        import RMF
        import IMP.rmf
        IMP.rmf.save_frame(self.dictionary_rmfs[name],nframe)
        self.dictionary_rmfs[name].flush()

    def write_rmfs(self,nframe):
        import RMF
        import IMP.rmf
        for rmf in self.dictionary_rmfs.keys():
            self.write_rmf(rmf,nframe)

    def init_stat(self,name,listofobjects):
        if self.ascii:
            flstat=open(name,'w')
            flstat.close()
        else:
            flstat=open(name,'wb')
            flstat.close()

        #check that all objects in listofobjects have a  get_output method

        for l in listofobjects:
            if not "get_output" in dir(l):
                print "Output: object ", l, " doesn't have get_output() method"
                exit()
        self.dictionary_stats[name]=listofobjects
    
    def set_output_entry(self,dictionary):
        self.initoutput.update(dictionary)

    def write_stat(self,name,appendmode=True):
        output=self.initoutput
        for obj in self.dictionary_stats[name]:
            output.update(obj.get_output())

        if appendmode:
           writeflag='a'
        else:
           writeflag='w'
           
        if self.ascii:
            flstat=open(name,writeflag)
            flstat.write("%s \n" % output)
            flstat.close()
        else:
            flstat=open(name,writeflag+'b')
            cPickle.dump(output,flstat,2)
            flstat.close()

    def write_stats(self):
        for stat in self.dictionary_stats.keys():
            self.write_stat(stat)

    def get_stat(self,name):
        output={}
        for obj in self.dictionary_stats[name]:
            output.update(obj.get_output())   
        return output  


class Variance():
    def __init__(self, model, tau, niter, prot, th_profile, write_data=False):
        self.model = model
        self.write_data=write_data
        self.tau = tau
        self.niter = niter
        #! select particles from the model
        particles=IMP.atom.get_by_type(prot, IMP.atom.ATOM_TYPE)
        self.particles = particles
        #store reference coordinates and theoretical profile
        self.refpos = [ IMP.core.XYZ(p).get_coordinates() for p in particles ]
        self.model_profile = th_profile

    def perturb_particles(self, perturb=True):
        for i,p in enumerate(self.particles):
            newpos = array(self.refpos[i])
            if perturb:
                newpos += random.normal(0,self.tau,3)
            newpos = IMP.algebra.Vector3D(newpos)
            IMP.core.XYZ(p).set_coordinates(newpos)

    def get_profile(self):
        model_profile = self.model_profile
        p=model_profile.calculate_profile(self.particles, IMP.saxs.CA_ATOMS)
        return array( [ model_profile.get_intensity(i) for i in
                        xrange(model_profile.size()) ] )

    def init_variances(self):
        #create placeholders
        N = self.model_profile.size()
        a = self.profiles[0][:]
        self.m = matrix(a).T # Nx1
        self.V = self.m * self.m.T
        self.normm = linalg.norm(self.m)
        self.normV = linalg.norm(self.V)

    def update_variances(self):
        a = matrix(self.profiles[-1]) #1xN
        n = float(len(self.profiles))
        self.m = a.T/n + (n-1)/n * self.m
        self.V = a.T*a + self.V
        self.oldnormm = self.normm
        self.oldnormV = self.normV
        self.normm = linalg.norm(self.m)
        self.normV = linalg.norm(self.V)
        self.diffm = (self.oldnormm-self.normm)/self.oldnormm
        self.diffV = (self.oldnormV-self.normV)/self.oldnormV

    def get_direct_stats(self, a):
        nq = len(a[0])
        nprof = len(a)
        m = [0]*nq
        for prof in a:
            for q,I in enumerate(prof):
                m[q] += I
        m = array(m)/nprof
        V = matrix(a)
        V = V.T*V
        Sigma = (matrix(a-m))
        Sigma = Sigma.T*Sigma/(nprof-1)
        mi = matrix(diag(1./m))
        Sigmarel = mi.T*Sigma*mi
        return m,V,Sigma,Sigmarel

    def store_data(self):
        if not os.path.isdir('data'):
            os.mkdir('data')
        profiles = matrix(self.profiles)
        self.directm, self.directV, self.Sigma, self.Sigmarel = \
                self.get_direct_stats(array(profiles))
        directV = self.directV
        #print "V comparison",(linalg.norm(directV-self.V)/self.normV)
        save('data/profiles', profiles)
        #absolute profile differences
        fl=open('data/profiles.dat','w')
        for i,l in enumerate(array(profiles).T):
            self.model_profile.get_q(i)
            fl.write('%s ' % i)
            for k in l:
                fl.write('%s ' % (k-self.directm[i]))
            fl.write('\n')
        #relative profile differences
        fl=open('data/profiles_rel.dat','w')
        for i,l in enumerate(array(profiles).T):
            self.model_profile.get_q(i)
            fl.write('%s ' % i)
            for k in l:
                fl.write('%s ' % ((k-self.directm[i])/self.directm[i]))
            fl.write('\n')
        save('data/m', self.directm)
        save('data/V', self.directV)
        Sigma = self.Sigma
        save('data/Sigma', Sigma)
        #Sigma matrix
        fl=open('data/Sigma.dat', 'w')
        model_profile = self.model_profile
        for i in xrange(model_profile.size()):
            qi = model_profile.get_q(i)
            for j in xrange(model_profile.size()):
                qj = model_profile.get_q(j)
                vij = self.Sigma[i,j]
                fl.write('%s %s %s\n' % (qi,qj,vij))
            fl.write('\n')
        #Sigma eigenvalues
        fl=open('data/eigenvals','w')
        for i in linalg.eigvalsh(Sigma):
            fl.write('%s\n' % i)
        Sigmarel = self.Sigmarel
        save('data/Sigmarel', Sigmarel)
        #Sigmarel matrix
        fl=open('data/Sigmarel.dat', 'w')
        model_profile = self.model_profile
        for i in xrange(model_profile.size()):
            qi = model_profile.get_q(i)
            for j in xrange(model_profile.size()):
                qj = model_profile.get_q(j)
                vij = self.Sigmarel[i,j]
                fl.write('%s %s %s\n' % (qi,qj,vij))
            fl.write('\n')
        #Sigma eigenvalues
        fl=open('data/eigenvals_rel','w')
        for i in linalg.eigvalsh(Sigmarel):
            fl.write('%s\n' % i)
        #mean profile
        fl=open('data/mean.dat','w')
        for i in xrange(len(self.directm)):
            qi = self.model_profile.get_q(i)
            fl.write('%s ' % qi)
            fl.write('%s ' % self.directm[i])
            fl.write('%s ' % sqrt(self.Sigma[i,i]))
            fl.write('\n')

    def try_chol(self, jitter):
        Sigma=self.Sigma
        try:
            linalg.cholesky(Sigma+matrix(eye(len(Sigma)))*jitter)
        except linalg.LinAlgError:
            print "Decomposition failed with jitter =",jitter
            return
        print "Successful decomposition with jitter =",jitter

    def run(self):
        self.profiles = [self.get_profile()]
        #self.init_variances()
        for n in xrange(self.niter):
            self.perturb_particles()
            self.profiles.append(self.get_profile())
            #self.update_variances()
            #profiles = matrix(self.profiles)
            #print n,self.diffm,self.diffV
        #print
        #
        if self.write_data:
            self.store_data()
        #self.try_chol(0.)
        #for i in logspace(-7,0,num=8):
        #    self.try_chol(i)

    def get_cov(self, relative=True):
        if not relative:
            return self.Sigma
        else:
            return self.Sigmarel

    #-------------------------------

def get_cross_link_data(directory,filename,(distmin,distmax,ndist),
                                             (omegamin,omegamax,nomega),
                                            (sigmamin,sigmamax,nsigma),
                                            don=None,doff=None,prior=0,type_of_profile="gofr"):

    filen=IMP.isd2.get_data_path("CrossLinkPMFs.dict")
    xlpot=open(filen)

    for line in xlpot:
        dictionary=eval(line)
        break

    xpot=dictionary[directory][filename]["distance"]
    pot=dictionary[directory][filename][type_of_profile]

    dist_grid=tools.get_grid(distmin, distmax, ndist, False)
    omega_grid=tools.get_log_grid(omegamin, omegamax, nomega)
    sigma_grid=tools.get_log_grid(sigmamin, sigmamax, nsigma)
    
    if don!=None and doff!=None:
       xlmsdata=IMP.isd2.CrossLinkData(dist_grid,omega_grid,sigma_grid,xpot,pot,don,doff,prior)
    else:
       xlmsdata=IMP.isd2.CrossLinkData(dist_grid,omega_grid,sigma_grid,xpot,pot)       
    return xlmsdata

    #-------------------------------


def get_cross_link_data_from_length(length,(distmin,distmax,ndist),
                               (omegamin,omegamax,nomega),
                               (sigmamin,sigmamax,nsigma)):

    dist_grid=tools.get_grid(distmin, distmax, ndist, False)
    omega_grid=tools.get_log_grid(omegamin, omegamax, nomega)
    sigma_grid=tools.get_log_grid(sigmamin, sigmamax, nsigma)

    xlmsdata=IMP.isd2.CrossLinkData(dist_grid,omega_grid,sigma_grid,length)
    return xlmsdata


def get_grid(gmin,gmax,ngrid,boundaries):
    grid=[]
    dx = ( gmax - gmin ) / float(ngrid)
    for i in range(0,ngrid+1):
        if(not boundaries and i==0): continue
        if(not boundaries and i==ngrid): continue
        grid.append( gmin + float(i) * dx )
    return grid

    #-------------------------------

def get_log_grid(gmin,gmax,ngrid):
    grid=[]
    for i in range(0,ngrid+1):
        grid.append( gmin*exp(float(i)/ngrid*log(gmax/gmin)) )
    return grid

    #-------------------------------


def get_drmsd(prot0, prot1):
    drmsd=0.; npairs=0.;
    for i in range(0,len(prot0)-1):
        for j in range(i+1,len(prot0)):
            dist0=IMP.core.get_distance(prot0[i],prot0[j])
            dist1=IMP.core.get_distance(prot1[i],prot1[j])
            drmsd+=(dist0-dist1)**2
            npairs+=1.
    return math.sqrt(drmsd/npairs)

    #-------------------------------

def get_residue_index_and_chain_from_particle(p):
    rind=IMP.atom.Residue(IMP.atom.Atom(p).get_parent()).get_index()
    c=IMP.atom.Residue(IMP.atom.Atom(p).get_parent()).get_parent()
    cid=IMP.atom.Chain(c).get_id()
    return rind,cid

def set_floppy_body(p):
    if IMP.core.RigidMember.particle_is_instance(p):
        rb=IMP.core.RigidMember(p).get_rigid_body()
        rb.set_is_rigid_member(p.get_index(),False)

    #-------------------------------
    
def select_calpha_or_residue(prot,chain,resid,ObjectName="None:",SelectResidue=False):
                    #use calphas
                    p=None
                    s=IMP.atom.Selection(prot, chains=chain,
                         residue_index=resid, atom_type=IMP.atom.AT_CA)
                    
                    ps=s.get_selected_particles()
                    #check if the calpha selection is empty
                    if ps:
                      if len(ps)==1: 
                        p=ps[0] 
                      else:
                        print ObjectName+" multiple residues selected for selection residue %s chain %s " % (resid,chain) 
                    else:
                       #use the residue, in case of simplified representation
                       s=IMP.atom.Selection(prot, chains=chain,
                           residue_index=resid)
                       ps=s.get_selected_particles()  
                       #check if the residue selection is empty                       
                       if ps:
                          if len(ps)==1: 
                             p=ps[0] 
                          else:
                             print ObjectName+" multiple residues selected for selection residue %s chain %s " % (resid,chain) 
                       
                       else:
                          print ObjectName+" residue %s chain %s does not exist" % (resid,chain) 
                    return p
                          

########################
### Tools to simulate data
########################

def normal_density_function(expected_value,sigma,x):
    return 1/math.sqrt(2*math.pi)/sigma*math.exp(-(x-expected_value)**2/2/sigma/sigma)

def log_normal_density_function(expected_value,sigma,x):
    return 1/math.sqrt(2*math.pi)/sigma/x*math.exp(-(math.log(x/expected_value)**2/2/sigma/sigma))

def get_random_data_point(expected_value,ntrials,sensitivity,sigma,outlierprob,begin_end_nbins_tuple,log=False,loggrid=False):
    
    begin=begin_end_nbins_tuple[0]
    end=begin_end_nbins_tuple[1]    
    nbins=begin_end_nbins_tuple[2]  
        
    if not loggrid:
       fmod_grid=get_grid(begin,end,nbins,True)    
    else:
       fmod_grid=get_log_grid(begin,end,nbins)
   
    
    norm=0
    cumul=[]
    cumul.append(0)
    
    a=[]
    for i in range(0,ntrials):
        a.append([random.random(),True])    
    
    if sigma != 0.0:
      for j in range(1,len(fmod_grid)):
        fj=fmod_grid[j]                                                    
        fjm1=fmod_grid[j-1]                                                
        df = fj - fjm1                                                     
        
        if not log:                                                          
           pj=normal_density_function(expected_value,sigma,fj)                                    
           pjm1=normal_density_function(expected_value,sigma,fjm1)
        else:
           pj=log_normal_density_function(expected_value,sigma,fj)                                    
           pjm1=log_normal_density_function(expected_value,sigma,fjm1)           
                                                                                 
        norm+= (pj+pjm1)/2.0*df;  
        cumul.append(norm)  
        #print fj, pj
           
      random_points=[] 
        
      for i in range(len(cumul)):
        #print i,a, cumul[i], norm
        for aa in a: 
            if (aa[0]<=cumul[i]/norm and aa[1]): 
               random_points.append(int(fmod_grid[i]/sensitivity)*sensitivity)
               aa[1]=False 

    else:
      random_points=[expected_value]*ntrials 
      
      
         

    for i in range(len(random_points)):
      if random.random() < outlierprob:       
         a=random.uniform(begin,end)
         random_points[i]=int(a/sensitivity)*sensitivity
    print random_points
    '''     
    for i in range(ntrials):
      if random.random() > OUTLIERPROB_:
        r=truncnorm.rvs(0.0,1.0,expected_value,BETA_)
        if r>1.0: print r,expected_value,BETA_
      else:
        r=random.random()
      random_points.append(int(r/sensitivity)*sensitivity)  
    '''
    
    rmean=0.; rmean2=0.
    for r in random_points:
        rmean+=r
        rmean2+=r*r

    rmean/=float(ntrials)
    rmean2/=float(ntrials)
    stddev=math.sqrt(max(rmean2-rmean*rmean,0.))
    return rmean,stddev

############################
#####Analysis tools
############################

# ----------------------------------
class GetModelDensity():
    def __init__(self, prot, dens_thresh=0.1, margin=20., voxel=5.):
        self.prot= prot
        self.dens_thresh= dens_thresh
        self.margin= margin
        self.voxel= voxel
        self.mgr= None
        self.densities= {}

    def get_grid_termini(self):
        minx,maxx,miny,maxy,minz,maxz = inf,-inf,inf,-inf,inf,-inf
        for p in IMP.atom.get_leaves(self.prot):
            a = IMP.core.XYZ(p)
            if a.get_x()<minx: minx=a.get_x()
            if a.get_x()>maxx: maxx=a.get_x()
            if a.get_y()<miny: miny=a.get_y()
            if a.get_y()>maxy: maxy=a.get_y()
            if a.get_z()<minz: minz=a.get_z()
            if a.get_z()>maxz: maxz=a.get_z()
        minx-=self.margin
        maxx+=self.margin
        miny-=self.margin
        maxy+=self.margin
        minz-=self.margin
        maxz+=self.margin
        mgr= mgrid[minx:maxx:self.voxel,\
                   miny:maxy:self.voxel,\
                   minz:maxz:self.voxel]
        mgr= reshape(mgr, (3,-1)).T
        self.mgr= mgr
        return self.mgr

    def set_mgr(self,mgr): self.mgr = mgr
        
    def get_subunit_density(self,name):
        coords= []
        radii= []
        for part in [IMP.atom.get_leaves(c) for c in self.prot.get_children()\
                     if c.get_name()==name][-1]:
            p= IMP.core.XYZR(part)
            coords.append(array([p.get_x(),p.get_y(),p.get_z()]))
            radii.append(p.get_radius())
        coords= array(coords)
        radii= array(radii)
        dists= cdist(self.mgr, coords)-radii
        dens= set(list(argwhere(dists<0)[:,0]))
        return dens

    def get_subunits_densities(self):
        for subunit in self.prot.get_children():
            subname= subunit.get_name()
            dens= self.get_subunit_density(subname)
            if subname not in self.densities:
                self.densities[subname]= array([1 if i in dens else 0 for i in xrange(len(self.mgr))])
            else:
                self.densities[subname]+= array([1 if i in dens else 0 for i in xrange(len(self.mgr))])
            #print self.densities[subname],self.densities[subname].max(),subname
        return self.densities

    def update_dict(self, dendict):
        self.densities= deepcopy(dendict)

    def write_mrc(self, outname):
        for subunit in self.densities:
            mdl= IMP.Model()
            apix=self.voxel
            resolution=6.
            bbox= IMP.algebra.BoundingBox3D(IMP.algebra.Vector3D(\
                          self.mgr[:,0].min(),self.mgr[:,1].min(),self.mgr[:,2].min()),\
                          IMP.algebra.Vector3D(\
                          self.mgr[:,0].max(),self.mgr[:,1].max(),self.mgr[:,2].max()))
            dheader = IMP.em.create_density_header(bbox,apix)
            dheader.set_resolution(resolution)

            dmap = IMP.em.SampledDensityMap(dheader)        
            ps = []
            freqs= self.densities[subunit]
            for x,i in enumerate(self.mgr):
                if freqs[x]==0.: continue
                p=IMP.Particle(mdl)
                IMP.core.XYZR.setup_particle(p,\
                                     IMP.algebra.Sphere3D(i,\
                                     1.))#freqs[x]))
                s=IMP.atom.Mass.setup_particle(p,freqs[x])
                ps.append(p)
            dmap.set_particles(ps)
            dmap.resample()
            dmap.calcRMS() # computes statistic stuff about the map and insert it in the header
            #print subunit, len(ps)
            IMP.em.write_map(dmap,outname+"_"+subunit+".mrc",IMP.em.MRCReaderWriter())



# ----------------------------------
class Clustering():

    def __init__(self):
        self.all_coords = {}

    def set_prot(self, prot):
        self.prot = prot    

    def get_subunit_coords(self,frame, align=0):
        coords= []
        for part in IMP.atom.get_leaves(self.prot):
            p= IMP.core.XYZR(part)
            #coords.append(array([p.get_x(),p.get_y(),p.get_z()]))
            coords.append(p.get_coordinates())
        #coords= array(coords)
	self.all_coords[frame]= coords
        
    def rmsd(self,mtr1,mtr2):
        return sqrt(sum(diagonal(cdist(mtr1,mtr2)**2)) / len(mtr1))
        #return IMP.atom.get_rmsd(mtr1,mtr2)

    def set_template(self, part_coords):
        self.tmpl_coords = part_coords

    def align_and_fill(self, frame, coords, assmb):
        transformation = IMP.algebra.get_transformation_aligning_first_to_second(coords,self.tmpl_coords)
        print IMP.atom.get_rmsd(coords, self.tmpl_coords),'###',
        coords = [transformation.get_transformed(n) for n in coords]
        assmb_coords = [transformation.get_transformed(IMP.core.XYZ(n).get_coordinates()) \
                        for n in IMP.atom.get_leaves(assmb)]
        print transformation,'###', IMP.atom.get_rmsd(coords, self.tmpl_coords)
        self.all_coords[frame]= assmb_coords

    def dist_matrix(self):
        K= self.all_coords.keys()
        M = zeros((len(K), len(K)))
        for f1 in xrange(len(K)-1):
            for f2 in xrange(f1,len(K)):
                r= self.rmsd(self.all_coords[K[f1]], self.all_coords[K[f2]])
                M[f1,f2]= r
                M[f2,f1]= r
                
        print M.max()
        from scipy.cluster import hierarchy as hrc
        import pylab as pl
        import pickle
        C = hrc.fclusterdata(M,0.5)
        outf = open('tmp_cluster_493.pkl','w')
        pickle.dump((K,M),outf)
        outf.close()
        #exit()
        C = list(argsort(C))
        M= M[C,:][:,C]
        M[0,0]=60.
        fig = pl.figure()
        ax = fig.add_subplot(111)
        cax = ax.imshow(M, interpolation='nearest')
        ax.set_yticks(range(len(K)))
        ax.set_yticklabels( [K[i] for i in C] )
        fig.colorbar(cax)
        pl.show()

# ----------------------------------
class GetModelDensity2():
    def __init__(self, align=0, dens_thresh=0.1, margin=20., voxel=5.):

        self.dens_thresh= dens_thresh
        self.margin= margin
        self.voxel= voxel
        self.mgr= None
        self.align= align
        self.densities= {}

    def set_align(ali):
        self.align = ali

    def set_grid(self, part_coords):
        coords = array([array(list(j)) for j in part_coords])
        minx,maxx,miny,maxy,minz,maxz = min(coords[:,0]),max(coords[:,0]),\
                                        min(coords[:,1]),max(coords[:,1]),\
                                        min(coords[:,2]),max(coords[:,2])
        minx-=self.margin
        maxx+=self.margin
        miny-=self.margin
        maxy+=self.margin
        minz-=self.margin
        maxz+=self.margin
        grid= mgrid[minx:maxx:self.voxel,\
                   miny:maxy:self.voxel,\
                   minz:maxz:self.voxel]
        grid= reshape(grid, (3,-1)).T
        self.grid= grid
        return self.grid

    def set_template(self, part_coords):
        self.tmpl_coords = part_coords

    def align_and_add(self, coords, prot):
        transformation = IMP.algebra.get_transformation_aligning_first_to_second(coords,self.tmpl_coords)
        print IMP.atom.get_rmsd(coords, self.tmpl_coords),'###',
        coords = [transformation.get_transformed(n) for n in coords]
        print transformation,'###', IMP.atom.get_rmsd(coords, self.tmpl_coords)
        self.get_subunits_densities(prot, transformation)

    def only_add(self, coords, prot):
       transformation = '' 
       self.get_subunits_densities(prot, transformation)

    def get_subunit_density(self,name, prot, transformation):
        crds= []
        radii= []
        
        for part in [IMP.atom.get_leaves(c) for c in prot.get_children()\
                     if c.get_name()==name][-1]:
            p= IMP.core.XYZR(part)
            if transformation!='': crds.append(array(list(transformation.get_transformed((p.get_x(),p.get_y(),p.get_z())))))
            else:  crds.append(array([p.get_x(),p.get_y(),p.get_z()]))
            radii.append(p.get_radius())
        '''
        for subunit in prot.get_children():
            for sbu in subunit.get_children():
                subname= sbu.get_name()
                if subname==name: 
                    for part in IMP.atom.get_leaves(sbu):
                        p= IMP.core.XYZR(part)
                        crds.append(array(list(transformation.get_transformed((p.get_x(),p.get_y(),p.get_z())))))
                        radii.append(p.get_radius())                    
        '''
        crds= array(crds)
        radii= array(radii)
        dists= cdist(self.grid, crds)-radii
        dens= set(list(argwhere(dists<0)[:,0]))
        return dens

    def get_subunits_densities(self, prot, transformation):
        for sbu in prot.get_children():
            if 1:#for sbu in subunit.get_children():
                subname= sbu.get_name()
                dens= self.get_subunit_density(subname, prot, transformation)
                if subname not in self.densities:
                    self.densities[subname]= array([1 if i in dens else 0 for i in xrange(len(self.grid))])
                else:
                    self.densities[subname]+= array([1 if i in dens else 0 for i in xrange(len(self.grid))])
        return self.densities

    def write_mrc(self, outname):
        for subunit in self.densities:
            mdl= IMP.Model()
            apix=self.voxel
            resolution=6.
            bbox= IMP.algebra.BoundingBox3D(IMP.algebra.Vector3D(\
                          self.grid[:,0].min(),self.grid[:,1].min(),self.grid[:,2].min()),\
                          IMP.algebra.Vector3D(\
                          self.grid[:,0].max(),self.grid[:,1].max(),self.grid[:,2].max()))
            dheader = IMP.em.create_density_header(bbox,apix)
            dheader.set_resolution(resolution)

            dmap = IMP.em.SampledDensityMap(dheader)        
            ps = []
            freqs= self.densities[subunit]
            for x,i in enumerate(self.grid):
                if freqs[x]==0.: continue
                p=IMP.Particle(mdl)
                IMP.core.XYZR.setup_particle(p,\
                                     IMP.algebra.Sphere3D(i,\
                                     1.))#freqs[x]))
                s=IMP.atom.Mass.setup_particle(p,freqs[x])
                ps.append(p)
            dmap.set_particles(ps)
            dmap.resample()
            dmap.calcRMS() # computes statistic stuff about the map and insert it in the header
            #print subunit, len(ps)
            IMP.em.write_map(dmap,outname+"_"+subunit+".mrc",IMP.em.MRCReaderWriter())


# ----------------------------------
from operator import itemgetter
class GetContactMap():
    def __init__(self, distance=15.):
        self.distance = distance
        self.contactmap = ''
        self.namelist = []

    def set_prot(self, prot):
        self.prot = prot    

    def get_subunit_coords(self,frame, align=0):
        coords= []
        namelist = []
        for part in self.prot.get_children():
            SortedSegments = []
            for chl in part.get_children():
                start = IMP.atom.get_leaves(chl)[0]
                end   = IMP.atom.get_leaves(chl)[-1]

                startres = IMP.atom.Fragment(start).get_residue_indexes()[0]
                endres   = IMP.atom.Fragment(end).get_residue_indexes()[-1]
                SortedSegments.append((chl,startres))
            SortedSegments = sorted(SortedSegments, key=itemgetter(1))
            for sgmnt in SortedSegments:
                for leaf in IMP.atom.get_leaves(sgmnt[0]):
                    p= IMP.core.XYZR(leaf) 
                    coords.append(array([p.get_x(),p.get_y(),p.get_z()]))
                    namelist.append(part.get_name()+'_'+sgmnt[0].get_name()+\
                                    '_'+str(IMP.atom.Fragment(leaf).get_residue_indexes()[0]))
	coords = array(coords)
        if len(self.namelist)==0: 
            self.namelist = namelist
            self.contactmap = zeros((len(coords), len(coords)))
        distances = cdist(coords, coords)<=self.distance
        self.contactmap += distances
        
    def dist_matrix(self):
        K= self.namelist
        M= self.contactmap
        C,R = [],[]
        for x,k in enumerate(K):
            if x==0: continue
            else: 
                sb = k.split('_')[0]
                sbp= K[x-1].split('_')[0]
                if sb!=sbp:
                    C.append(sbp)
                    R.append(x)
        C.append(sbp)
        R.append(x)
        W = []
        for x,r in enumerate(R):
            if x==0: W.append(r)
            else: W.append(r-R[x-1])
        print W

        import matplotlib.pyplot as plt
        import matplotlib.gridspec as gridspec

        f = plt.figure()
        gs = gridspec.GridSpec(10, 10,
                       width_ratios=W,
                       height_ratios=W
                       )
 
        cnt = 0
        for x1,r1 in enumerate(R):
            if x1==0: s1=0
            else: s1 = R[x1-1]
            for x2,r2 in enumerate(R):
                if x2==0: s2=0
                else: s2 = R[x2-1]

	        ax = plt.subplot(gs[cnt])
                ax.set_yticks([])
                ax.set_xticks([])
                cax = ax.imshow(log(M[s1:r1,s2:r2]), interpolation='nearest')
                cnt+=1
        plt.show()
 
        '''
        fig = pl.figure()
        ax = fig.add_subplot(111)
        cax = ax.imshow(log(M), interpolation='nearest')

        ax.set_yticks( R )
        ax.set_yticklabels( C )
        fig.colorbar(cax)
        pl.show()
        '''


