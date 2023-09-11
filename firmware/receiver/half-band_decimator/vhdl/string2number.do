# Library
vlib work
vcom -2008 -work work ./string2number.vhd
vsim -voptargs="+acc" -t ps work.string2number
run 10 ns