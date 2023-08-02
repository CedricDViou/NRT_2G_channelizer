with open("../vhdl/HB_decimator.vhd", 'rt') as fid:
    # only parse ENTITY/GENERIC
    l = fid.readline()
    while "GENERIC" not in l.upper():
        l = fid.readline()
    while "PORT" not in l.upper():
        if "_w" in l or "_dp" in l:
            l = l.replace(": integer :=", '=')
            exec(l)
        l = fid.readline().strip()


signals = {
    'din'    : (g_din_w, g_din_dp),
    'pre_add': (g_din_w+1, g_din_dp),
    'coef'   : (g_coef_w, g_coef_dp),
    'mult'   : (g_din_w+1+g_coef_w, g_din_dp+g_coef_dp),
    'acc'    : (g_acc_w, g_acc_dp),
    'dout'   : (g_dout_w, g_dout_dp),
           }

max_name_width = 0
max_int_size = 0
max_frac_size = 0
for signal, Q in signals.items():
    name = f"{signal}"
    max_name_width = max(len(name), max_name_width)
    int_size = Q[0] - Q[1]
    frac_size = Q[1]
    max_int_size = max(int_size, max_int_size)
    max_frac_size = max(frac_size, max_frac_size)

max_field_width = max_name_width + len(" Q(00,00): ")

head0 = "-- " + " " * (max_field_width) + " "
head1 = head0
for dec in range(max_int_size, 0, -1):
    dec_str = f"{dec:>2}"
    head0 += dec_str[0]
    head1 += dec_str[1]
head0 += " "
head1 += "."
for dec in range(1, max_frac_size+1):
    dec_str = f"{dec:>2}"
    head0 += dec_str[0]
    head1 += dec_str[1]
head0 += " "
head1 += " "


print(head0)
print(head1)
for signal, Q in signals.items():
    int_size = Q[0] - Q[1]
    frac_size = Q[1]
    print(f"-- {signal:{max_name_width}s} Q({Q[0]:2},{Q[1]:2}): |{'_' * int_size:>{max_int_size}s}.{'_' * frac_size:{max_frac_size}s}|")
