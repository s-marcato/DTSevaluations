###DTS script to extract single fly data from a DTS XML file and claculate some derivative variables needed later
#extract fly meta-data
fly <- singleflydata[[3]]
flyname = fly$name[1]
if(exists("flynames")){flynames[l,x] = paste(flyname)} #copy the name into the list of all flynames

#extract sequence meta-data
NofPeriods = singleflydata[[5]]
sequence <- singleflydata[[6]]
samplerate = as.numeric(as.character(singleflydata[[4]]$sample_rate))
real_sample_rate = as.numeric(as.character(singleflydata[[11]]))
down_sample_rate = as.numeric(as.character(singleflydata[[12]]))
nonOMperiods=which(!grepl("optomotor", sequence$type)==TRUE) #vector containing period numbers for non-optomotor periods
testperiods=which((sequence$type=="color" | sequence$type=="fs" | sequence$type=="yt" | sequence$type=="sw") & sequence$outcome=="0") #vector containing all testperiods
pretestperiods=as.vector(unlist(split(testperiods, cumsum(c(1, diff(testperiods) != 1)))[1]))

#extract experiment meta-data
experimenter <- singleflydata[[2]]
experiment <- singleflydata[[4]]

#extract rawdata
rawdata <- singleflydata[[9]]
flyrange = singleflydata[[10]]
traces <- singleflydata[[13]]
#calculate max fly values for axes when plotting
maxfly = c(-round_any(max(abs(flyrange)), 100, f=ceiling)*0.9,round_any(max(abs(flyrange)), 100, f=ceiling)*0.9)

#create/empty the dataframe for dwellmeans
Dwell = any(c("yt","color","sw","fs") %in% sequence$type) ###determine if dwelling times should be calculated
if (Dwell & l==1){
  dwellmeans = list()
  dwellmeans$unpunished <- dwellmeans$punished <- data.frame(matrix(ncol = NofPeriods))
}